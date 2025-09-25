"""
Smart Stock Movement Node - Single Node Approach
Handles parsing, validation, auto-population, and creation in one place.
Only requires item code and quantity - everything else is auto-populated.
"""

import json
import re
from typing import Dict, Any, List, Tuple
from loguru import logger
from langchain_core.runnables import RunnableConfig
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import AIMessage

from megamind.clients.mcp_client_manager import client_manager
from megamind.configuration import Configuration
from ...states import StockMovementState


def _create_auto_populated_stock_entry(
    company: str, item_code: str, quantity: float
) -> Dict[str, Any]:
    """
    Auto-populate all Stock Entry fields from minimal user input.
    Core business logic for warehouse selection and field population.
    """
    source_warehouse, target_warehouse = _get_default_warehouses(company)

    return {
        "doctype": "Stock Entry",
        "stock_entry_type": "Material Transfer",
        "company": company,
        "items": [
            {
                "item_code": item_code,
                "qty": quantity,
                "s_warehouse": source_warehouse,
                "t_warehouse": target_warehouse,
                "uom": "Nos",
            }
        ],
    }


def _get_default_warehouses(company: str) -> Tuple[str, str]:
    """
    Get default source and target warehouses for a company.
    Business logic: Always transfer from Main Store to Branch Store.
    """
    source_warehouse = f"{company} - Main Store"
    target_warehouse = f"{company} - Branch Store"
    return source_warehouse, target_warehouse


async def _extract_stock_request(
    messages: List[Any], model_name: str
) -> Dict[str, Any]:
    """
    Extract item code and quantity from natural language input using LLM.
    Uses separate internal LLM instance to avoid streaming to client.
    """

    # Get the last user message
    user_message = ""
    for msg in reversed(messages):
        if hasattr(msg, "content") and not isinstance(msg, AIMessage):
            user_message = str(msg.content).strip()
            break

    # If no valid user message found, use fallback
    if not user_message:
        logger.warning("No valid user message found, using fallback extraction")
        return {"item_code": "unknown", "quantity": 1, "operation_type": "transfer"}

    extraction_prompt = f"""
Хэрэглэгчийн асуултаас дараах мэдээллийг гарга:

Асуулт: "{user_message}"

Гаргах ёстой мэдээлэл:
- item_code: барааны код эсвэл нэр (жишээ: "SKU001", "Nike гутал", "MAM4-BLA-36⅔")
- quantity: тоо хэмжээ (зөвхөн тоо) 
- operation_type: "transfer" (үргэлж)

JSON форматаар хариулна уу. Жишээ:
{{"item_code": "SKU001", "quantity": 10, "operation_type": "transfer"}}

Хэрэв тоо хэмжээ тодорхойгүй бол quantity: 1 гэж тавь.
"""

    # Validate extraction prompt is not empty
    if not extraction_prompt.strip():
        logger.warning("Empty extraction prompt, using fallback")
        return _fallback_extraction(user_message)

    try:
        # Create completely isolated internal LLM instance for extraction only
        # This prevents any streaming of internal processing messages to client
        internal_llm = ChatGoogleGenerativeAI(
            model=model_name,
            temperature=0.1,
            max_retries=1,
            disable_streaming=True,  # Correct parameter for disabling streaming
            verbose=False,  # Disable verbose output
            callbacks=[],  # Empty callbacks to prevent any streaming callbacks
        )

        # Use HumanMessage instead of SystemMessage for better compatibility
        from langchain_core.messages import HumanMessage

        # Create proper message format
        messages_for_llm = [HumanMessage(content=extraction_prompt)]

        # Direct invoke without streaming - use invoke with config to ensure no streaming
        try:
            # Use invoke with explicit config to disable streaming
            result = internal_llm.invoke(
                messages_for_llm, config={"configurable": {"streaming": False}}
            )
        except:
            # Fallback to async if sync fails, also with streaming disabled
            result = await internal_llm.ainvoke(
                messages_for_llm, config={"configurable": {"streaming": False}}
            )

        # Try to parse JSON from the response
        response_text = result.content if result and hasattr(result, "content") else ""

        if not response_text:
            raise ValueError("Empty response from LLM")

        # Extract JSON from response (handle cases where LLM adds extra text)
        json_match = re.search(r"\{.*\}", response_text, re.DOTALL)
        if json_match:
            json_str = json_match.group(0)
            extracted_data = json.loads(json_str)

            # Validate extracted data
            if "item_code" not in extracted_data:
                extracted_data["item_code"] = "unknown"
            if "quantity" not in extracted_data:
                extracted_data["quantity"] = 1
            if "operation_type" not in extracted_data:
                extracted_data["operation_type"] = "transfer"

            return extracted_data
        else:
            # Fallback: try to extract using regex
            return _fallback_extraction(user_message)

    except Exception as e:
        logger.error(f"LLM extraction failed: {e}")
        return _fallback_extraction(user_message)


def _fallback_extraction(user_message: str) -> Dict[str, Any]:
    """
    Fallback extraction using regex patterns when LLM fails.
    """
    # Try to find item code patterns first - improved for special characters
    item_patterns = [
        r"([A-Za-z0-9\-⅔]+)\s*бараанаас",  # "MAM4-BLA-36⅔ бараанаас"
        r"([A-Za-z0-9\-⅔]+)\s*кодтой",  # "SKU001 кодтой"
        r"([A-Za-z0-9\-⅔]+)\s*барaa",  # "SKU001 баранаа"
        r"([A-Za-z0-9\-⅔]+)\s*барааг",  # "MAM4-BLA-36⅔ барааг"
        r"([A-Za-z0-9\-⅔]+)",  # Any alphanumeric code with special chars
    ]

    item_code = "unknown"
    item_match_span = (0, 0)  # Track where we found the item code

    for pattern in item_patterns:
        match = re.search(pattern, user_message)
        if match:
            item_code = match.group(1)
            item_match_span = match.span()
            break

    # Try to find quantity - but avoid the item code area
    quantity_patterns = [
        r"(\d+)\s*ширхэг",  # "10 ширхэг"
        r"(\d+)\s*pieces",  # "10 pieces"
        r"(\d+)\s*(?:units|ширхэг|pieces)",  # "10 units/ширхэг/pieces"
        r"(?:^|\s)(\d+)(?:\s|$)",  # Standalone number (not part of item code)
    ]

    quantity = 1
    for pattern in quantity_patterns:
        for match in re.finditer(pattern, user_message):
            # Skip if this number is inside the item code
            match_start, match_end = match.span(1) if match.lastindex else match.span()
            if match_start >= item_match_span[1] or match_end <= item_match_span[0]:
                # This number is not part of the item code
                quantity = int(match.group(1))
                break
        if quantity != 1:  # If we found a quantity, stop looking
            break

    return {"item_code": item_code, "quantity": quantity, "operation_type": "transfer"}


async def _validate_and_search_item(
    item_code: str, mcp_tools: List[Any]
) -> Dict[str, Any]:
    """
    Validate item exists and search for it using list_documents MCP tool.
    Searches by both item_code and item_name with exact and partial matches.
    """
    try:
        # Find the list_documents tool
        list_documents_tool = None
        for tool in mcp_tools:
            if hasattr(tool, "name") and tool.name == "list_documents":
                list_documents_tool = tool
                break

        if not list_documents_tool:
            logger.error("list_documents tool not found in MCP tools")
            return {
                "item_code": item_code,
                "item_name": "",
                "uom": "Nos",
                "found": False,
                "error": "list_documents tool not available",
                "match_type": "error",
            }

        # Step 1: Try exact match by item_code
        try:
            result = await list_documents_tool.ainvoke(
                {
                    "doctype": "Item",
                    "filters": {"item_code": item_code},
                    "fields": ["name", "item_name", "item_code", "stock_uom"],
                    "limit": 1,
                }
            )

            if result and len(result) > 0:
                item = result[0]
                return {
                    "item_code": item["item_code"],
                    "item_name": item.get("item_name", ""),
                    "uom": item.get("stock_uom", "Nos"),
                    "found": True,
                    "match_type": "exact_code",
                }
        except Exception as e:
            logger.debug(f"Exact item_code match failed: {e}")

        # Step 2: Try exact match by item_name
        try:
            result = await list_documents_tool.ainvoke(
                {
                    "doctype": "Item",
                    "filters": {"item_name": item_code},
                    "fields": ["name", "item_name", "item_code", "stock_uom"],
                    "limit": 1,
                }
            )

            if result and len(result) > 0:
                item = result[0]
                return {
                    "item_code": item["item_code"],
                    "item_name": item.get("item_name", ""),
                    "uom": item.get("stock_uom", "Nos"),
                    "found": True,
                    "match_type": "exact_name",
                }
        except Exception as e:
            logger.debug(f"Exact item_name match failed: {e}")

        # Step 3: Try partial match by item_code
        try:
            result = await list_documents_tool.ainvoke(
                {
                    "doctype": "Item",
                    "filters": {"item_code": ["like", f"%{item_code}%"]},
                    "fields": ["name", "item_name", "item_code", "stock_uom"],
                    "limit": 5,
                }
            )

            if result and len(result) > 0:
                # Return the first match (most relevant)
                item = result[0]
                return {
                    "item_code": item["item_code"],
                    "item_name": item.get("item_name", ""),
                    "uom": item.get("stock_uom", "Nos"),
                    "found": True,
                    "match_type": "partial_code",
                    "all_matches": result,
                }
        except Exception as e:
            logger.debug(f"Partial item_code match failed: {e}")

        # Step 4: Try partial match by item_name
        try:
            result = await list_documents_tool.ainvoke(
                {
                    "doctype": "Item",
                    "filters": {"item_name": ["like", f"%{item_code}%"]},
                    "fields": ["name", "item_name", "item_code", "stock_uom"],
                    "limit": 5,
                }
            )

            if result and len(result) > 0:
                # Return the first match (most relevant)
                item = result[0]
                return {
                    "item_code": item["item_code"],
                    "item_name": item.get("item_name", ""),
                    "uom": item.get("stock_uom", "Nos"),
                    "found": True,
                    "match_type": "partial_name",
                    "all_matches": result,
                }
        except Exception as e:
            logger.debug(f"Partial item_name match failed: {e}")

        # If all searches fail, return not found
        logger.info(f"Item not found in any search: {item_code}")
        return {
            "item_code": item_code,
            "item_name": "",
            "uom": "Nos",
            "found": False,
            "match_type": "none",
        }

    except Exception as e:
        logger.error(f"Item validation failed: {e}")
        return {
            "item_code": item_code,
            "item_name": "",
            "uom": "Nos",
            "found": False,
            "error": str(e),
            "match_type": "error",
        }


def _format_success_message(
    result: Dict[str, Any], item_info: Dict[str, Any], quantity: float
) -> str:
    """
    Format success message in Mongolian with table format.
    """
    entry_id = result.get("name", "Unknown")
    item_code = item_info.get("item_code", "Unknown")
    item_name = item_info.get("item_name", "")

    # Create table format
    message = f"""✅ Бараа материалын хөдөлгөөн үүсгэгдлээ!

📋 Мэдээлэл:
ID: {entry_id}
Бараа: {item_code}"""

    if item_name:
        message += f" ({item_name})"

    message += f"""
Тоо хэмжээ: {int(quantity)} ширхэг
Эх агуулах: Төв агуулах
Зорилтот агуулах: Салбар агуулах

🎯 Амжилттай шилжүүллээ!"""

    return message


def _format_error_message(error_info: Dict[str, Any]) -> str:
    """
    Format error message in Mongolian with helpful suggestions.
    """
    error_type = error_info.get("error_type", "unknown")

    if error_type == "item_not_found":
        return f"""❌ Барааны код олдсонгүй: {error_info.get('item_code', 'Unknown')}

💡 Зөвлөгөө:
• Барааны кодыг дахин шалгана уу
• Барааны нэрээр хайж үзнэ үү  
• Жишээ: "Nike гутал", "Samsung утас" гэх мэт"""

    elif error_type == "validation_error":
        return f"""❌ Баталгаажуулалтын алдаа: {error_info.get('message', 'Unknown error')}

💡 Шийдвэрлэх арга:
• Оруулсан мэдээллээ дахин шалгана уу
• Барааны код зөв эсэхийг шалгана уу"""

    else:
        return f"""❌ Алдаа гарлаа: {error_info.get('message', 'Тодорхойгүй алдаа')}

💡 Дахин оролдоно уу эсвэл системийн админтай холбогдоно уу."""


async def smart_stock_movement_node(
    state: StockMovementState, config: RunnableConfig
) -> Dict[str, Any]:
    """
    Intelligent stock movement node that handles everything in one place.
    Only asks for item code and quantity - everything else is auto-populated.
    """
    logger.debug("---SMART STOCK MOVEMENT NODE---")

    # Get configuration and setup
    configurable = Configuration.from_runnable_config(config)
    company = state.get("company")
    messages = state.get("messages", [])

    # Validate company exists
    if not company:
        logger.warning("Company not found, trying to get default company")
        try:
            from megamind.clients.frappe_client import FrappeClient

            frappe_client = FrappeClient()
            company = frappe_client.get_default_company()
            if not company:
                return {
                    "messages": [
                        AIMessage(
                            content="Компанийн мэдээлэл олдсонгүй. Системийн админтай холбогдоно уу."
                        )
                    ]
                }
        except Exception as e:
            return {
                "messages": [
                    AIMessage(content=f"Компанийн мэдээлэл авахад алдаа гарлаа: {e}")
                ]
            }

    # Get MCP client and tools
    mcp_client = client_manager.get_client()
    mcp_tools = await mcp_client.get_tools()
    llm = ChatGoogleGenerativeAI(model=configurable.query_generator_model)

    try:
        # Step 1: Extract user intent using internal LLM (separate instance)
        logger.info("Extracting stock request from user input...")
        extracted_data = await _extract_stock_request(
            messages, configurable.query_generator_model
        )
        logger.info(f"Extracted data: {extracted_data}")

        # Step 2: Validate and search item
        logger.info(f"Validating item: {extracted_data['item_code']}")
        item_info = await _validate_and_search_item(
            extracted_data["item_code"], mcp_tools
        )

        if not item_info["found"]:
            logger.warning(f"Item not found: {extracted_data['item_code']}")
            return {
                "messages": [
                    AIMessage(
                        content=_format_error_message(
                            {
                                "error_type": "item_not_found",
                                "item_code": extracted_data["item_code"],
                            }
                        )
                    )
                ]
            }

        # Step 3: Auto-populate stock entry using business logic
        logger.info("Auto-populating stock entry...")
        stock_entry_data = _create_auto_populated_stock_entry(
            company, item_info["item_code"], extracted_data["quantity"]
        )

        # Update UOM if we found it during validation
        if item_info.get("uom"):
            stock_entry_data["items"][0]["uom"] = item_info["uom"]

        logger.info(f"Auto-populated stock entry: {stock_entry_data}")

        # Step 4: Enhanced pre-validation (if available)
        try:
            # Find validate_document_enhanced tool
            validate_tool = None
            for tool in mcp_tools:
                if hasattr(tool, "name") and tool.name == "validate_document_enhanced":
                    validate_tool = tool
                    break

            if validate_tool:
                validation_result = await validate_tool.ainvoke(
                    {
                        "doctype": "Stock Entry",
                        "values": stock_entry_data,
                        "context": {
                            "isNew": True,
                            "company": company,
                            "includeWarnings": True,
                            "includeSuggestions": True,
                        },
                    }
                )

                if validation_result and not validation_result.get("is_valid", True):
                    logger.warning(f"Validation failed: {validation_result}")
                    return {
                        "messages": [
                            AIMessage(
                                content=_format_error_message(
                                    {
                                        "error_type": "validation_error",
                                        "message": validation_result.get(
                                            "message", "Validation failed"
                                        ),
                                    }
                                )
                            )
                        ]
                    }
        except Exception as e:
            # If enhanced validation is not available, continue without it
            logger.debug(f"Enhanced validation not available: {e}")

        # Step 5: Create Stock Entry
        logger.info("Creating Stock Entry...")

        # Find create_document tool
        create_tool = None
        for tool in mcp_tools:
            if hasattr(tool, "name") and tool.name == "create_document":
                create_tool = tool
                break

        if not create_tool:
            logger.error("create_document tool not found in MCP tools")
            return {
                "messages": [
                    AIMessage(
                        content=_format_error_message(
                            {
                                "error_type": "system_error",
                                "message": "create_document tool not available",
                            }
                        )
                    )
                ]
            }

        result = await create_tool.ainvoke(
            {"doctype": "Stock Entry", "values": stock_entry_data}
        )

        if result:
            logger.info(f"Stock Entry created successfully: {result.get('name')}")

            # Format success message
            success_message = _format_success_message(
                result, item_info, extracted_data["quantity"]
            )

            return {
                "company": company,
                "last_stock_entry_id": result.get("name"),
                "messages": [AIMessage(content=success_message)],
                "performance_metrics": {
                    "operation": "stock_transfer",
                    "success": True,
                    "item_code": item_info["item_code"],
                    "quantity": extracted_data["quantity"],
                },
            }
        else:
            return {
                "messages": [
                    AIMessage(
                        content=_format_error_message(
                            {
                                "error_type": "creation_error",
                                "message": "Stock Entry үүсгэхэд алдаа гарлаа",
                            }
                        )
                    )
                ]
            }

    except Exception as e:
        logger.error(f"Smart stock movement node failed: {e}")
        return {
            "messages": [
                AIMessage(
                    content=_format_error_message(
                        {"error_type": "system_error", "message": str(e)}
                    )
                )
            ]
        }

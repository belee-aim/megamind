# Stock Movement Agent Implementation

## Overview

This document describes the implementation of a specialized stock movement agent for the ERPNext integration system. The agent is designed to handle inventory transfers, stock movements, and warehouse operations with enhanced performance and specialized knowledge.

## Architecture Changes

### 1. New Agent Node
- **File**: `src/megamind/graph/nodes/stock_movement_agent.py`
- **Purpose**: Specialized agent focused on inventory and stock movement operations
- **Capabilities**: Stock Entry, Material Transfer, Stock Reconciliation

### 2. Enhanced Router Logic
- **File**: `src/megamind/graph/nodes/router.py`
- **Change**: Updated to support 3-way routing (rag_node, agent_node, stock_movement_agent_node)
- **Intelligence**: Automatically detects inventory-related queries and routes appropriately

### 3. Updated Graph Builder
- **File**: `src/megamind/graph/builder.py`
- **Changes**: 
  - Added stock movement agent node
  - Implemented separate tool routing for each agent
  - Updated conditional edges for proper flow control

### 4. New Dedicated Endpoint
- **Endpoint**: `/api/v1/stock-movement/stream`
- **Purpose**: Direct routing to stock movement agent for faster processing
- **Benefit**: Bypasses router for known stock movement operations

## Key Features

### Specialized Prompts
The stock movement agent uses specialized prompts that focus on:
- **Stock Entry**: Material receipt, material issue, material transfer, repack
- **Material Transfer**: Moving items between warehouses
- **Stock Reconciliation**: Adjusting stock quantities and valuations
- **Inventory Management**: Stock levels, item tracking, batch and serial number management

### Intelligent Routing
The router now intelligently detects queries related to:
- Inventory operations
- Stock movements
- Material transfers
- Stock reconciliation

### Tool Integration
- **General Agent**: Full access to both `frappe_retriever` and `erpnext_mcp_tool`
- **Stock Movement Agent**: Only uses `erpnext_mcp_tool` for ERPNext operations
- **RAG Node**: Uses `frappe_retriever` for document operations
- Proper tool routing back to the originating agent

## API Endpoints

### 1. Dedicated Stock Movement Endpoint
```
POST /api/v1/stock-movement/stream
```
**Body:**
```json
{
  "question": "transfer 50 units from Warehouse A to Warehouse B"
}
```
**Note**: This endpoint automatically routes to the stock movement agent.

## Usage Examples

### Stock Entry Creation
```bash
curl -X POST "http://localhost:8000/api/v1/stock-movement/stream" \
  -H "Content-Type: application/json" \
  -H "Cookie: sid=your-session-id" \
  -d '{
    "question": "Create a stock entry for material receipt of 100 units of Item-001 in Main Warehouse"
  }'
```

### Material Transfer
```bash
curl -X POST "http://localhost:8000/api/v1/stock-movement/stream" \
  -H "Content-Type: application/json" \
  -H "Cookie: sid=your-session-id" \
  -d '{
    "question": "Transfer 25 units of Item-002 from Warehouse A to Warehouse B"
  }'
```

### Stock Reconciliation
```bash
curl -X POST "http://localhost:8000/api/v1/stock-movement/stream" \
  -H "Content-Type: application/json" \
  -H "Cookie: sid=your-session-id" \
  -d '{
    "question": "Reconcile stock for Item-003, current quantity is 150 units"
  }'
```

## Router Intelligence

The router automatically detects and routes the following types of queries:

### To Stock Movement Agent
- "create a stock entry"
- "transfer materials between warehouses"
- "reconcile stock"
- "check inventory levels"
- "move items to different warehouse"
- "create material receipt"
- "update stock quantities"
- "material transfer from warehouse A to B"


## Performance Benefits

1. **Faster Processing**: Direct routing eliminates router overhead for known stock movement operations
2. **Specialized Knowledge**: Focused prompts provide better context for inventory operations
3. **Reduced Latency**: Dedicated endpoint bypasses general routing logic
4. **Better Accuracy**: Specialized agent understands inventory terminology and workflows

## Backward Compatibility

- Existing `/api/v1/stream` endpoint continues to work unchanged
- General agent still handles non-inventory operations
- RAG node functionality remains intact
- All existing integrations continue to function

## Testing

Run the test suite to verify the implementation:

```bash
python test_stock_movement_agent.py
```

The test suite verifies:
- File structure integrity
- Route schema validation
- Prompt definitions
- Router logic
- Graph building capabilities

## Deployment Notes

1. **Environment Variables**: No new environment variables required
2. **Dependencies**: Uses existing MCP tools and Frappe client
3. **Database**: No schema changes required
4. **Configuration**: Uses existing configuration system

## Monitoring and Logging

The stock movement agent includes comprehensive logging:
- Agent node execution: `---STOCK MOVEMENT AGENT NODE---`
- Tool routing decisions
- Error handling and recovery
- Performance metrics

## Future Enhancements

Potential areas for future improvement:
1. **Batch Operations**: Support for bulk inventory operations
2. **Advanced Analytics**: Inventory trend analysis and predictions
3. **Integration Webhooks**: Real-time inventory updates
4. **Mobile Optimization**: Specialized mobile endpoints for warehouse operations
5. **Audit Trail**: Enhanced tracking of inventory changes

## Troubleshooting

### Common Issues

1. **Import Errors**: Ensure all dependencies are installed
2. **Routing Issues**: Check router prompt configuration
3. **Tool Access**: Verify MCP client connectivity
4. **Session Management**: Ensure proper cookie handling

### Debug Mode

Enable debug logging to troubleshoot issues:
```python
import logging
logging.getLogger("megamind").setLevel(logging.DEBUG)
```

## Conclusion

The stock movement agent implementation provides a specialized, high-performance solution for inventory and warehouse operations while maintaining the existing architecture's flexibility and extensibility. The implementation follows best practices for separation of concerns and maintains backward compatibility with existing systems.

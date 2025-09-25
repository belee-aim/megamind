"""
Enhanced error handling for the stock movement agent.
This module provides smart error categorization, suggestions, and recovery mechanisms.
"""

from typing import Dict, List, Any
from enum import Enum


class ErrorType(Enum):
    """Types of errors that can occur in stock movement operations."""
    VALIDATION_ERROR = "validation_error"
    PERMISSION_ERROR = "permission_error"
    BUSINESS_RULE_ERROR = "business_rule_error"
    DATA_ERROR = "data_error"
    WORKFLOW_ERROR = "workflow_error"
    SYSTEM_ERROR = "system_error"


class ErrorSeverity(Enum):
    """Severity levels for errors and warnings."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class EnhancedErrorHandler:
    """
    Enhanced error handler with smart categorization and suggestions.
    Implements Phase 3 enhancements from the improvement plan.
    """
    
    def __init__(self):
        self.error_patterns = self._load_error_patterns()
        self.suggestion_engine = SuggestionEngine()
    
    def categorize_error(self, error_message: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Categorize an error message and provide smart suggestions.
        
        Args:
            error_message: The error message to categorize
            context: Additional context about the error
            
        Returns:
            Dict containing error type, severity, suggestions, and recovery options
        """
        context = context or {}
        
        # Determine error type
        error_type = self._determine_error_type(error_message)
        
        # Determine severity
        severity = self._determine_severity(error_message, error_type)
        
        # Generate suggestions
        suggestions = self.suggestion_engine.generate_suggestions(
            error_message, error_type, context
        )
        
        # Generate recovery options
        recovery_options = self._generate_recovery_options(error_type, context)
        
        return {
            "error_type": error_type.value,
            "severity": severity.value,
            "categorized_message": self._format_error_message(error_message, error_type),
            "suggestions": suggestions,
            "recovery_options": recovery_options,
            "context": context,
            "timestamp": self._get_timestamp()
        }
    
    def handle_validation_result(self, validation_result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle enhanced validation results from validate_document_enhanced.
        
        Args:
            validation_result: Result from validate_document_enhanced tool
            
        Returns:
            Formatted error and warning information
        """
        handled_result = {
            "errors": [],
            "warnings": [],
            "suggestions": [],
            "business_rules": []
        }
        
        # Process errors
        for error in validation_result.get("errors", []):
            categorized_error = self.categorize_error(
                error.get("message", "Unknown error"),
                {"field": error.get("field"), "validation_type": error.get("type")}
            )
            handled_result["errors"].append(categorized_error)
        
        # Process warnings
        for warning in validation_result.get("warnings", []):
            categorized_warning = {
                "field": warning.get("field"),
                "type": warning.get("type"),
                "message": warning.get("message"),
                "severity": warning.get("severity", "medium"),
                "suggestions": self.suggestion_engine.generate_suggestions(
                    warning.get("message", ""), ErrorType.BUSINESS_RULE_ERROR, warning
                )
            }
            handled_result["warnings"].append(categorized_warning)
        
        # Process suggestions
        for suggestion in validation_result.get("suggestions", []):
            handled_result["suggestions"].append(suggestion)
        
        return handled_result
    
    def _determine_error_type(self, error_message: str) -> ErrorType:
        """Determine the type of error based on the message."""
        error_message_lower = error_message.lower()
        
        if any(keyword in error_message_lower for keyword in ["permission", "access", "unauthorized"]):
            return ErrorType.PERMISSION_ERROR
        elif any(keyword in error_message_lower for keyword in ["validation", "required", "invalid"]):
            return ErrorType.VALIDATION_ERROR
        elif any(keyword in error_message_lower for keyword in ["workflow", "state", "submit"]):
            return ErrorType.WORKFLOW_ERROR
        elif any(keyword in error_message_lower for keyword in ["business rule", "policy", "restriction"]):
            return ErrorType.BUSINESS_RULE_ERROR
        elif any(keyword in error_message_lower for keyword in ["not found", "does not exist", "missing"]):
            return ErrorType.DATA_ERROR
        else:
            return ErrorType.SYSTEM_ERROR
    
    def _determine_severity(self, error_message: str, error_type: ErrorType) -> ErrorSeverity:
        """Determine the severity of an error."""
        if error_type == ErrorType.SYSTEM_ERROR:
            return ErrorSeverity.CRITICAL
        elif error_type == ErrorType.PERMISSION_ERROR:
            return ErrorSeverity.HIGH
        elif error_type == ErrorType.VALIDATION_ERROR:
            return ErrorSeverity.MEDIUM
        elif error_type == ErrorType.WORKFLOW_ERROR:
            return ErrorSeverity.MEDIUM
        elif error_type == ErrorType.BUSINESS_RULE_ERROR:
            return ErrorSeverity.LOW
        else:
            return ErrorSeverity.MEDIUM
    
    def _format_error_message(self, error_message: str, error_type: ErrorType) -> str:
        """Format error message with user-friendly language."""
        formatted_message = error_message
        
        # Add Mongolian translations for common errors
        if error_type == ErrorType.VALIDATION_ERROR:
            if "required" in error_message.lower():
                formatted_message += " (Энэ талбар заавал бөглөх шаардлагатай)"
            elif "invalid" in error_message.lower():
                formatted_message += " (Буруу утга оруулсан байна)"
        
        elif error_type == ErrorType.PERMISSION_ERROR:
            formatted_message += " (Та энэ үйлдлийг хийх эрхгүй байна)"
        
        elif error_type == ErrorType.DATA_ERROR:
            formatted_message += " (Мэдээлэл олдсонгүй)"
        
        return formatted_message
    
    def _generate_recovery_options(self, error_type: ErrorType, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate recovery options based on error type."""
        recovery_options = []
        
        if error_type == ErrorType.VALIDATION_ERROR:
            recovery_options.append({
                "action": "validate_input",
                "description": "Оруулсан мэдээллээ дахин шалгана уу",
                "automated": False
            })
        
        elif error_type == ErrorType.PERMISSION_ERROR:
            recovery_options.append({
                "action": "check_permissions",
                "description": "Системийн админтай холбогдон эрх авна уу",
                "automated": False
            })
        
        elif error_type == ErrorType.DATA_ERROR:
            recovery_options.append({
                "action": "search_alternatives",
                "description": "Өөр хайлтын үг ашиглан дахин оролдоно уу",
                "automated": True
            })
        
        return recovery_options
    
    def _load_error_patterns(self) -> Dict[str, List[str]]:
        """Load error patterns for categorization."""
        return {
            "validation": [
                "required field",
                "invalid format",
                "value out of range",
                "duplicate entry"
            ],
            "permission": [
                "access denied",
                "insufficient permissions",
                "unauthorized access"
            ],
            "workflow": [
                "invalid workflow state",
                "cannot submit",
                "workflow transition"
            ],
            "business_rule": [
                "business rule violation",
                "policy restriction",
                "compliance issue"
            ]
        }
    
    def _get_timestamp(self) -> str:
        """Get current timestamp."""
        from datetime import datetime
        return datetime.now().isoformat()


class SuggestionEngine:
    """
    Engine for generating smart suggestions based on errors and context.
    """
    
    def generate_suggestions(self, error_message: str, error_type: ErrorType, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate smart suggestions based on error context."""
        suggestions = []
        
        if error_type == ErrorType.VALIDATION_ERROR:
            suggestions.extend(self._generate_validation_suggestions(error_message, context))
        
        elif error_type == ErrorType.DATA_ERROR:
            suggestions.extend(self._generate_data_suggestions(error_message, context))
        
        elif error_type == ErrorType.PERMISSION_ERROR:
            suggestions.extend(self._generate_permission_suggestions(error_message, context))
        
        return suggestions
    
    def _generate_validation_suggestions(self, error_message: str, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate suggestions for validation errors."""
        suggestions = []
        
        field = context.get("field", "")
        
        if "item_code" in field.lower():
            suggestions.append({
                "type": "field_suggestion",
                "field": field,
                "message": "Барааны кодыг зөв оруулна уу. Жишээ: ABC123",
                "example": "ABC123"
            })
        
        elif "warehouse" in field.lower():
            suggestions.append({
                "type": "field_suggestion",
                "field": field,
                "message": "Агуулахын нэрийг бүрэн оруулна уу",
                "example": "Төв агуулах"
            })
        
        elif "qty" in field.lower():
            suggestions.append({
                "type": "field_suggestion",
                "field": field,
                "message": "Тоо хэмжээ нь 0-ээс их байх ёстой",
                "example": "50"
            })
        
        return suggestions
    
    def _generate_data_suggestions(self, error_message: str, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate suggestions for data errors."""
        suggestions = []
        
        if "item" in error_message.lower():
            suggestions.append({
                "type": "search_suggestion",
                "message": "Барааны нэр эсвэл брендээр хайж үзнэ үү",
                "action": "enhanced_search"
            })
        
        elif "warehouse" in error_message.lower():
            suggestions.append({
                "type": "search_suggestion",
                "message": "Агуулахын жагсаалтыг шалгана уу",
                "action": "list_warehouses"
            })
        
        return suggestions
    
    def _generate_permission_suggestions(self, error_message: str, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate suggestions for permission errors."""
        suggestions = []
        
        suggestions.append({
            "type": "permission_suggestion",
            "message": "Системийн админтай холбогдож шаардлагатай эрхийг авна уу",
            "action": "contact_admin"
        })
        
        return suggestions

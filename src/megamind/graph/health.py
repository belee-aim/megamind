# src/megamind/graph/health.py
async def agent_health_check():
    """Monitor agent health and performance"""
    health_status = {
        'rag_agent': await check_rag_health(),
        'general_agent': await check_general_health(),
        'stock_movement_agent': await check_stock_movement_health(),
        'mcp_connection': await check_mcp_health(),
        'database': await check_db_health()
    }
    return health_status

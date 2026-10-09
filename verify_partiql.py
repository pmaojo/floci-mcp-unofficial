from tools.dynamodb import register
class DummyMCP:
    def tool(self):
        def decorator(func):
            return func
        return decorator
mcp = DummyMCP()
register(mcp)
print("Registration successful")

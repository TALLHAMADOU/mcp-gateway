"""Example plugin: Math utilities"""

from src.plugin_registry import tool


@tool(name="add", description="Add two numbers")
def add(a: float, b: float) -> float:
    """
    Sum two numbers.
    
    Args:
        a: First number
        b: Second number
    
    Returns:
        Sum of a and b
    """
    return a + b


@tool(name="fibonacci", description="Generate Fibonacci sequence")
def fibonacci(n: int) -> list:
    """
    Generate first n Fibonacci numbers.
    
    Args:
        n: Number of Fibonacci numbers to generate
    
    Returns:
        List of Fibonacci numbers
    """
    if n <= 0:
        return []
    elif n == 1:
        return [0]
    
    fib = [0, 1]
    for i in range(2, n):
        fib.append(fib[-1] + fib[-2])
    return fib[:n]



from mcp.server.fastmcp import FastMCP, Context
from contextlib import asynccontextmanager
from typing import AsyncIterator, Dict, Any, List, Optional
import asyncio

import json
from browser_use.browser.browser import Browser, BrowserConfig, BrowserContextConfig
from browser_use.browser.context import BrowserContext
from browser_use.controller.service import Controller
from browser_use.controller.registry.views import ActionModel

import sys
import logging



# Use the right import for StreamHandler
# StreamHandler is in the main logging module, not in logging.handlers
# from logging.handlers import StreamHandler  # This is incorrect
# Instead, use:

# Configure a custom stderr handler for all logging
stderr_handler = logging.StreamHandler(sys.stderr)  # This is correct
stderr_handler.setFormatter(logging.Formatter("%(levelname)-8s [%(name)s] %(message)s"))

# Get the root logger and remove any existing handlers
root_logger = logging.getLogger()
root_logger.handlers = []
root_logger.addHandler(stderr_handler)
root_logger.setLevel(logging.INFO)

# Create our specific logger
logger = logging.getLogger("browser-agent")

# Force all loggers from third-party libraries to use stderr too
for third_party_logger_name in [
    "playwright", "httpx", "selenium", "asyncio", "browser_use", 
    "mcp", "langchain", "openai", "anthropic"
]:
    third_party_logger = logging.getLogger(third_party_logger_name)
    third_party_logger.handlers = []
    third_party_logger.addHandler(stderr_handler)
    third_party_logger.setLevel(logging.WARNING)  # Only show warnings and errors
    third_party_logger.propagate = False  # Don't propagate to root logger


CHROME_BROWSER = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

    
@asynccontextmanager
async def browser_lifespan(server: FastMCP) -> AsyncIterator[Dict[str, Any]]:
    """Manage browser lifecycle"""
    browser = Browser(
        config=BrowserConfig(
            headless=False,  # This is True in production
            disable_security=True,
            chrome_instance_path=CHROME_BROWSER,
            new_context_config=BrowserContextConfig(
                disable_security=True,
                minimum_wait_page_load_time=1,  # 3 on prod
                maximum_wait_page_load_time=10,  # 20 on prod
                # no_viewport=True,
                browser_window_size={
                    'width': 1280,
                    'height': 1100,
                },
                save_recording_path='./tmp/recordings',
                # trace_path="./tmp/result_processing",
            ),
	    )
    )
    browser_context = await browser.new_context()
    controller = Controller()
    
    try:
        yield {
            "browser": browser,
            "browser_context": browser_context,
            "controller": controller
        }
    finally:
        await browser_context.close()
        await browser.close()

# Initialize FastMCP server
mcp = FastMCP("browser-agent", lifespan=browser_lifespan)

@mcp.tool()
async def get_available_actions(ctx: Context) -> str:
    """Get the list of available browser actions."""
    controller = ctx.request_context.lifespan_context["controller"]
    return controller.registry.get_prompt_description()

@mcp.tool()
async def get_browser_state(ctx: Context) -> str:
    """Get the current browser state."""
    browser_context = ctx.request_context.lifespan_context["browser_context"]
    
    try:
        state = await browser_context.get_state()
        elements_text = state.element_tree.clickable_elements_to_string()
        
        return f"""
Current URL: {state.url}
Title: {state.title}
Available tabs: {[tab.model_dump() for tab in state.tabs]}
Interactive elements:
{elements_text}
"""
    except Exception as e:
        logger.error(f"Error getting browser state: {str(e)}")
        return f"Error getting browser state: {str(e)}"

@mcp.tool()
async def execute_action(action_name: str, params: Dict[str, Any], ctx: Context) -> str:
    """Execute a browser action.
    
    Args:
        action_name: The name of the action to execute
        params: The parameters for the action
    """
    browser_context = ctx.request_context.lifespan_context["browser_context"]
    controller = ctx.request_context.lifespan_context["controller"]
    
    try:
        # Create action model
        action_model = controller.registry.create_action_model()(**{action_name: params})
        
        # Execute the action
        result = await controller.act(
            action_model,
            browser_context
        )
        
        # Return the result
        if result.extracted_content:
            return result.extracted_content
        elif result.error:
            return f"Error: {result.error}"
        else:
            return f"Action {action_name} executed successfully"
    except Exception as e:
        logger.error(f"Error executing action: {str(e)}")
        return f"Error executing action: {str(e)}"

@mcp.tool()
async def execute_multiple_actions(actions: List[Dict[str, Any]], ctx: Context) -> str:
    """Execute multiple browser actions in sequence.
    
    Args:
        actions: List of action objects, each with "name" and "params" fields
    """
    browser_context = ctx.request_context.lifespan_context["browser_context"]
    controller = ctx.request_context.lifespan_context["controller"]
    
    results = []
    
    try:
        for action_obj in actions:
            if "name" not in action_obj or "params" not in action_obj:
                results.append(f"Error: Invalid action format. Must include 'name' and 'params'.")
                continue
                
            action_name = action_obj["name"]
            params = action_obj["params"]
            
            # Create action model
            action_model = controller.registry.create_action_model()(**{action_name: params})
            
            # Execute the action
            result = await controller.act(
                action_model,
                browser_context
            )
            
            
            # Store the result
            if result.extracted_content:
                results.append(result.extracted_content)
            elif result.error:
                results.append(f"Error: {result.error}")
                # Break on error
                break
            else:
                results.append(f"Action {action_name} executed successfully")
                
        return "\n".join(results)
    except Exception as e:
        logger.error(f"Error executing multiple actions: {str(e)}")
        return f"Error executing multiple actions: {str(e)}"

@mcp.tool()
async def navigate_to_url(url: str, ctx: Context) -> str:
    """Navigate to a URL.
    
    Args:
        url: The URL to navigate to
    """
    browser_context = ctx.request_context.lifespan_context["browser_context"]
    controller = ctx.request_context.lifespan_context["controller"]
    
    try:
        # Create action model
        action_model = controller.registry.create_action_model()(go_to_url={"url": url})
        
        # Execute the action
        result = await controller.act(
            action_model,
            browser_context
        )
        
        # Return the result
        if result.extracted_content:
            return result.extracted_content
        elif result.error:
            return f"Error: {result.error}"
        else:
            return f"Navigated to {url} successfully"
    except Exception as e:
        logger.error(f"Error navigating to URL: {str(e)}")
        return f"Error navigating to URL: {str(e)}"

@mcp.tool()
async def click_element(index: int, ctx: Context) -> str:
    """Click an element on the page.
    
    Args:
        index: The index of the element to click
    """
    browser_context = ctx.request_context.lifespan_context["browser_context"]
    controller = ctx.request_context.lifespan_context["controller"]
    
    try:
        # Create action model
        action_model = controller.registry.create_action_model()(click_element={"index": index})
        
        # Execute the action
        result = await controller.act(
            action_model,
            browser_context
        )
        
        # Return the result
        if result.extracted_content:
            return result.extracted_content
        elif result.error:
            return f"Error: {result.error}"
        else:
            return f"Clicked element with index {index} successfully"
    except Exception as e:
        logger.error(f"Error clicking element: {str(e)}")
        return f"Error clicking element: {str(e)}"

@mcp.tool()
async def input_text(index: int, text: str, ctx: Context) -> str:
    """Input text into a field.
    
    Args:
        index: The index of the element
        text: The text to input
    """
    browser_context = ctx.request_context.lifespan_context["browser_context"]
    controller = ctx.request_context.lifespan_context["controller"]
    
    try:
        # Create action model
        action_model = controller.registry.create_action_model()(input_text={"index": index, "text": text})
        
        # Execute the action
        result = await controller.act(
            action_model,
            browser_context
        )
        
        # Return the result
        if result.extracted_content:
            return result.extracted_content
        elif result.error:
            return f"Error: {result.error}"
        else:
            return f"Input text '{text}' into element with index {index} successfully"
    except Exception as e:
        logger.error(f"Error inputting text: {str(e)}")
        return f"Error inputting text: {str(e)}"

@mcp.tool()
async def scroll_down(ctx: Context, amount: Optional[int] = None) -> str:
    """Scroll down the page.
    
    Args:
        amount: The number of pixels to scroll down. If None, scrolls down one page.
    """
    browser_context = ctx.request_context.lifespan_context["browser_context"]
    controller = ctx.request_context.lifespan_context["controller"]
    
    try:
        # Create action model
        action_model = controller.registry.create_action_model()(scroll_down={"amount": amount})
        
        # Execute the action
        result = await controller.act(
            action_model,
            browser_context
        )
        
        # Return the result
        if result.extracted_content:
            return result.extracted_content
        elif result.error:
            return f"Error: {result.error}"
        else:
            return f"Scrolled down successfully"
    except Exception as e:
        logger.error(f"Error scrolling down: {str(e)}")
        return f"Error scrolling down: {str(e)}"

@mcp.tool()
async def extract_content(goal: str, ctx: Context) -> str:
    """Extract content from the page based on a specific goal.
    
    Args:
        goal: The extraction goal
    """
    browser_context = ctx.request_context.lifespan_context["browser_context"]
    controller = ctx.request_context.lifespan_context["controller"]
    
    try:
        # Create action model
        action_model = controller.registry.create_action_model()(extract_content={"goal": goal})
        
        # Execute the action
        result = await controller.act(
            action_model,
            browser_context
        )
        
        # Return the result
        if result.extracted_content:
            return result.extracted_content
        elif result.error:
            return f"Error: {result.error}"
        else:
            return f"Extracted content successfully"
    except Exception as e:
        logger.error(f"Error extracting content: {str(e)}")
        return f"Error extracting content: {str(e)}"

# Start the server
if __name__ == "__main__":
    mcp.run(transport='stdio')
from pathlib import Path
import re
import yaml
import base64
import os
import logging
from typing import Dict, Any, Optional, Callable, TypeVar, Union
import traceback
from functools import wraps
from dataclasses import dataclass

# Constants
NEWSLETTER_TEMPLATE = "newsletter_template.html"
NEWSLETTER_OUTPUT = "newsletter_ready.html" 
NEWSLETTER_DATA = "newsletter_data.yaml"
CSS_VAR_PATTERN = r'--([a-zA-Z0-9-]+):\s*([^;]+);'
LOGO_CONTAINER_PATTERN = r'<div class="logo-container">.*?(<img[^>]*?src\s*=\s*["\']?\s*["\']?[^>]*?>)'
IMG_SRC_PATTERN = 'src=""'
BASE64_IMG_FORMAT = 'data:image/png;base64,{}'

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

# Type definitions
T = TypeVar('T')
HTMLContent = str
PlaceholderData = Dict[str, Any]


@dataclass
class NewsletterPaths:
    """Data class to store newsletter template paths."""
    template: Path
    output: Path
    data: Path
    
    @classmethod
    def from_strings(cls, template: str, output: str, data: str) -> 'NewsletterPaths':
        """Create a NewsletterPaths instance from string paths."""
        return cls(
            template=Path(template),
            output=Path(output),
            data=Path(data)
        )


def log_operation(operation_name: str) -> Callable:
    """Decorator to log operations and handle exceptions."""
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            try:
                result = func(*args, **kwargs)
                logger.info(f"{operation_name} completed successfully")
                return result
            except Exception as e:
                logger.error(f"{operation_name} failed: {e}")
                logger.debug(traceback.format_exc())
                raise
        return wrapper
    return decorator


class NewsletterGenerator:
    """A class to handle newsletter HTML generation with inline styles."""
    
    def __init__(
        self, 
        template_path: str = NEWSLETTER_TEMPLATE,
        output_path: str = NEWSLETTER_OUTPUT,
        data_path: str = NEWSLETTER_DATA
    ):
        """Initialize the newsletter generator with configurable paths."""
        self.paths = NewsletterPaths.from_strings(
            template=template_path,
            output=output_path,
            data=data_path
        )
    
    def convert_image_to_base64(self, image_path: str) -> str:
        """Convert an image file to base64 string."""
        try:
            with open(image_path, "rb") as img_file:
                return base64.b64encode(img_file.read()).decode('utf-8')
        except FileNotFoundError:
            logger.error(f"Image file not found: {image_path}")
            return ""
        except Exception as e:
            logger.error(f"Error converting image to base64: {e}")
            return ""

    def read_newsletter_data(self) -> PlaceholderData:
        """Read the newsletter data from YAML file."""
        self._validate_file_exists(self.paths.data, "Data file")
        
        with open(self.paths.data, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)

    def read_html_template(self) -> HTMLContent:
        """Read the HTML template file."""
        self._validate_file_exists(self.paths.template, "HTML template")
        
        with open(self.paths.template, "r", encoding="utf-8") as f:
            return f.read()
            
    def _validate_file_exists(self, file_path: Path, file_description: str) -> None:
        """Validate that a file exists or raise an appropriate exception."""
        if not file_path.exists():
            raise FileNotFoundError(f"{file_description} {file_path} does not exist")
        if not file_path.is_file():
            raise ValueError(f"{file_description} {file_path} is not a file")

    def process_logo_image(self, html_content: HTMLContent, newsletter_data: PlaceholderData) -> HTMLContent:
        """Process and embed the logo image as base64 in the HTML."""
        if 'logo_path' not in newsletter_data:
            return html_content
        
        logo_path = newsletter_data['logo_path']
        if not self._file_exists(logo_path):
            logger.warning(f"Logo file '{logo_path}' does not exist")
            return html_content
        
        # Convert logo to base64
        logo_base64 = self.convert_image_to_base64(logo_path)
        if not logo_base64:
            logger.warning("Failed to convert logo to base64")
            return html_content
        
        logger.info(f"Converted logo '{logo_path}' to base64")
        
        # Find and update the logo image tag
        return self._update_logo_image_tag(html_content, logo_base64)
        
    def _file_exists(self, file_path: Union[str, Path]) -> bool:
        """Check if a file exists."""
        return os.path.exists(file_path) and os.path.isfile(file_path)

    def _update_logo_image_tag(self, html_content: HTMLContent, logo_base64: str) -> HTMLContent:
        """Find and update the logo image tag with base64 data."""
        # Look for image tag in the logo-container div
        header_img_match = re.search(LOGO_CONTAINER_PATTERN, html_content, re.DOTALL)
        
        if not header_img_match:
            logger.warning(
                "Could not find the logo image tag in the HTML template. "
                "Please ensure there's a div with class='logo-container' "
                "containing an img tag with an empty src attribute."
            )
            return html_content
        
        # Replace the empty src with the base64 data
        header_img_tag = header_img_match.group(1)
        updated_header_img_tag = header_img_tag.replace(
            IMG_SRC_PATTERN, 
            f'src="{BASE64_IMG_FORMAT.format(logo_base64)}"'
        )
        
        updated_html = html_content.replace(header_img_tag, updated_header_img_tag)
        logger.info("Logo image src attribute updated with base64 data")
        
        return updated_html

    def replace_placeholders(self, html_content: HTMLContent, newsletter_data: PlaceholderData) -> HTMLContent:
        """Replace all placeholders in the HTML with data from the YAML file."""
        # Create a modified copy of the content
        modified_content = html_content
        
        for key, value in newsletter_data.items():
            if key == 'logo_path':
                # Skip logo_path as it's handled separately
                continue
                
            if isinstance(value, dict):
                # Handle nested dictionaries (like colors)
                modified_content = self._replace_nested_placeholders(modified_content, key, value)
            else:
                # Handle simple placeholders
                modified_content = self._replace_simple_placeholder(modified_content, key, value)
        
        logger.info("Placeholders replaced with newsletter data")
        return modified_content

    def _replace_nested_placeholders(self, html_content: HTMLContent, parent_key: str, 
                                    nested_dict: Dict[str, Any]) -> HTMLContent:
        """Replace placeholders for nested dictionary values."""
        modified_content = html_content
        
        for subkey, subvalue in nested_dict.items():
            placeholder = f"{{{{ {parent_key}.{subkey} }}}}"
            value_str = self._convert_to_string(subvalue)
            modified_content = modified_content.replace(placeholder, value_str)
            
        return modified_content

    def _replace_simple_placeholder(self, html_content: HTMLContent, key: str, value: Any) -> HTMLContent:
        """Replace a simple placeholder with its value."""
        placeholder = f"{{{{ {key} }}}}"
        value_str = self._convert_to_string(value)
        return html_content.replace(placeholder, value_str)
        
    def _convert_to_string(self, value: Any) -> str:
        """Convert any value to a string."""
        if isinstance(value, (int, float)):
            return str(value)
        return str(value) if value is not None else ""

    @log_operation("HTML preparation")
    def prepare_html(self) -> HTMLContent:
        """Read the HTML file, replace placeholders and insert base64 images."""
        # Read the template and data
        html_content = self.read_html_template()
        newsletter_data = self.read_newsletter_data()
        
        # Process logo image
        html_content = self.process_logo_image(html_content, newsletter_data)
        
        # Replace placeholders
        html_content = self.replace_placeholders(html_content, newsletter_data)
        
        return html_content

    @log_operation("CSS variable replacement")
    def replace_css_variables(self, html_content: HTMLContent) -> HTMLContent:
        """Replace CSS variables with actual color values for better email client compatibility."""
        # Extract CSS variable definitions
        css_vars = self._extract_css_variables(html_content)
        if not css_vars:
            logger.info("No CSS variables found to replace")
            return html_content
            
        # Create a modified copy of the content
        modified_content = html_content
        
        # Replace var() usage with the actual values
        for var_name, var_value in css_vars.items():
            modified_content = re.sub(f'var\\(--{var_name}\\)', var_value, modified_content)
        
        return modified_content
        
    def _extract_css_variables(self, html_content: HTMLContent) -> Dict[str, str]:
        """Extract CSS variable definitions from HTML content."""
        css_vars = {}
        for match in re.finditer(CSS_VAR_PATTERN, html_content):
            var_name = match.group(1)
            var_value = match.group(2).strip()
            css_vars[var_name] = var_value
        return css_vars

    @log_operation("CSS inlining")
    def inline_css(self, html_content: HTMLContent) -> HTMLContent:
        """Convert CSS to inline styles for better email client compatibility."""
        try:
            from premailer import Premailer
            return self._transform_with_premailer(html_content)
        except ImportError:
            logger.warning("Premailer not installed. CSS inlining skipped.")
            return html_content
            
    def _transform_with_premailer(self, html_content: HTMLContent) -> HTMLContent:
        """Transform HTML content using Premailer."""
        from premailer import Premailer
        
        transformer = Premailer(
            html=html_content,
            remove_classes=False,  # Keep classes for potential JS interactions
            keep_style_tags=True,  # Keep style tags as fallback
            strip_important=False, # Keep !important declarations
            base_url=None,         # For relative URLs if present
            disable_validation=True # Disable HTML validation for better performance
        )
        
        return transformer.transform()

    @log_operation("HTML saving")
    def save_html(self, html_content: HTMLContent) -> None:
        """Save the HTML content to the output file."""
        with open(self.paths.output, "w", encoding="utf-8") as f:
            f.write(html_content)

    @log_operation("Newsletter generation")
    def generate(self) -> None:
        """Generate the newsletter HTML with inline styles."""
        # Prepare the HTML with placeholders replaced
        html = self.prepare_html()
        
        # Replace CSS variables with actual values
        html = self.replace_css_variables(html)
        
        # Convert CSS to inline styles
        html = self.inline_css(html)
        
        # Save the processed HTML
        self.save_html(html)


def main() -> int:
    """Main entry point for the newsletter generator."""
    try:
        generator = NewsletterGenerator()
        generator.generate()
        return 0
    except Exception as e:
        logger.error(f"Newsletter generation failed: {e}")
        return 1


if __name__ == "__main__":
    exit(main())

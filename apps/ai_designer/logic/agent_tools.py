import os
import json
from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional
from langchain.tools import tool
from langchain_google_genai import ChatGoogleGenerativeAI
from . import api_services # Use relative import

# --- HELPER FUNCTIONS (UNCHANGED) ---
def _create_modifications_with_llm(property_data: dict, template: dict) -> List[Dict[str, Any]]:
    """Helper function to use an LLM for intelligent data mapping."""
    llm = ChatGoogleGenerativeAI(model="gemini-1.5-flash", temperature=0.0)
    modifiable_layers = template.get('available_modifications', [])
    prompt = f"""
    You are an expert data mapper for a real estate design tool. Your only job is to create a JSON list of modifications by mapping the provided PROPERTY DATA to the modifiable LAYERS of the provided TEMPLATE.

    ---
    DATA MAPPING GUIDE:
    Use this guide to understand how to map TEMPLATE layer names to the data paths in the PROPERTY DATA.
    {{
        "property_address": "address", "city": "city", "state": "state", "zip": "zip", "property_price": "price_display",
        "description": "description", "bedrooms": "bedrooms", "bathrooms": "bathrooms", "square_feet": "square_feet",
        "agent_name": "agents.listing_agent.name", "agent_contact": "agents.listing_agent.phone", "agent_email": "agents.listing_agent.email",
        "neighborhood": "geo_data.neighborhood_name", "brokerage_name": "agents.listing_agent.office.name", "property_type": "property_type",
        "property_image": "hero.large", "photo1": "photos[3].large", "photo2": "photos[4].large", "photo3": "photos[5].large",
        "agent_photo": null
    }}
    ---

    TASK: Based on the rules and data, generate the JSON list of modifications.

    PROPERTY DATA:
    {json.dumps(property_data, indent=2)}

    TEMPLATE (only modifiable layers are shown):
    {json.dumps(modifiable_layers, indent=2)}

    Instructions:
    1.  Create a JSON list of "modifications". Each modification is an object with "name" and "text" or "image_url".
    2.  Use the `DATA MAPPING GUIDE` and the live `PROPERTY DATA` to find the correct values.
    3.  If `PROPERTY DATA` contains extra user-provided fields (like `open_house_date`), map them to corresponding template layers.
    4.  If a value isn't available, omit that layer.
    5.  Respond ONLY with the raw JSON list. Do not add explanations or markdown.
    """
    try:
        response = llm.invoke(prompt)
        cleaned_response = response.content.strip().replace("```json", "").replace("```", "")
        return json.loads(cleaned_response)
    except Exception as e:
        print(f"Error during LLM mapping: {e}")
        return []

def _get_missing_fields(template: dict, property_data: dict) -> Dict[str, str]:
    """Identifies required template fields that are not present in the property data."""
    potential_user_fields = {
        "open_house_date": "the date of the open house (e.g., 'Saturday, June 15th')",
        "open_house_time": "the time of the open house (e.g., '2-4 PM')",
        "custom_headline": "a custom headline for the ad",
    }
    missing_fields = {}
    template_layer_names = [mod['name'] for mod in template.get('available_modifications', [])]
    for field_key, field_description in potential_user_fields.items():
        if field_key in template_layer_names and field_key not in property_data:
            missing_fields[field_key] = field_description
    return missing_fields


# --- THE SINGLE, CONSOLIDATED TOOL ---

class GenerateImageInput(BaseModel):
    mls_listing_id: str = Field(description="The unique Multiple Listing Service ID for the property.")
    mls_id: str = Field(description = "The 3-digit ID that represents all the listings in a specific region.")
    template_name: str = Field(description="The exact name of the design template chosen by the user.")
    user_provided_data: Optional[Dict[str, str]] = Field(None, description="A dictionary of extra information provided by the user after being prompted, e.g., {'open_house_date': 'Saturday at 2 PM'}.")

@tool(args_schema=GenerateImageInput)
def generate_marketing_image(mls_listing_id: str, mls_id: str, template_name: str, user_provided_data: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    """
    Generates a marketing image for a property. This single tool handles the entire generation process. It will fetch property data using the MLS details and the chosen template. If the template requires extra information (like an open house date), it will return a message asking for it. If all information is present, it will create and return the final image.
    """
    try:
        api_key = os.environ["BANNERBEAR_API_KEY"]
        
        # 1. Fetch all necessary data
        templates = api_services.fetch_all_template_details(api_key)
        property_data = api_services.fetch_realty_details(mls_listing_id, mls_id)
        
        if not templates: return {"status": "error", "message_for_user": "I couldn't find any design templates."}
        if not property_data: return {"status": "error", "message_for_user": f"I couldn't find data for MLS Listing ID {mls_listing_id} in MLS {mls_id}."}

        # 2. Find the selected template
        selected_template = next((t for t in templates if t["name"].lower() == template_name.lower()), None)
        if not selected_template:
            return {"status": "error", "message_for_user": f"I'm sorry, I couldn't find a template named '{template_name}'. Please choose from the available list."}

        # 3. Check if user has already provided extra data (follow-up call)
        if user_provided_data:
            property_data.update(user_provided_data)

        # 4. Check if the template still requires info the user hasn't provided yet
        missing_fields = _get_missing_fields(selected_template, property_data)
        if missing_fields:
            field_list = " and ".join(list(missing_fields.values()))
            user_message = f"To complete the '{selected_template['name']}' design, I just need a bit more information: {field_list}. Can you provide that for me?"
            
            return {
                "status": "needs_info",
                "message_for_user": user_message, 
                "context": {
                    "mls_listing_id": mls_listing_id, 
                    "mls_id": mls_id, 
                    "template_name": selected_template['name'] # Pass the exact name for the next call
                }
            }

        # 5. If all info is present, proceed with generation
        modifications = _create_modifications_with_llm(property_data, selected_template)
        if not modifications: return {"status": "error", "message_for_user": "I found the property data but couldn't map it to the design."}

        image_req = api_services.start_image_generation(api_key, selected_template['uid'], modifications)
        if not (polling_url := image_req.get("self")): return {"status": "error", "message_for_user": "Failed to start image generation."}
        
        final_image = api_services.poll_for_image(api_key, polling_url)
        if not final_image or not (image_url := final_image.get("image_url_png")):
            return {"status": "error", "message_for_user": "The final image rendering failed."}
            
        return {
            "status": "image_generated",
            "message_for_user": f"Using the '{selected_template['name']}' template, here is the design I created for you!\n\n![Generated Ad]({image_url})"
        }

    except Exception as e:
        print(f"A critical error occurred in generate_marketing_image: {e}")
        return {"status": "error", "message_for_user": f"A critical error occurred: {e}"}
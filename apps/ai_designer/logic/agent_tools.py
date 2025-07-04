import os
import json
from pydantic import BaseModel, Field
from typing import Dict, Any, List
from langchain.tools import tool
from langchain_google_genai import ChatGoogleGenerativeAI
from . import api_services # Use relative import

def _choose_best_template_with_llm(user_intent: str, templates: list) -> dict | None:
    """Helper function to use an LLM to semantically choose the best template."""
    llm = ChatGoogleGenerativeAI(model="gemini-1.5-flash", temperature=0.0)
    # Provide only name and UID for the LLM to choose from.
    template_summaries = json.dumps([{"uid": t["uid"], "name": t["name"]} for t in templates])
    
    prompt = f"""
    You are an expert at understanding user intent. Your only job is to select the single best template from a list that matches the user's request.
    
    USER'S REQUEST: "{user_intent}"
    
    AVAILABLE TEMPLATES: {template_summaries}
    
    Instructions:
    - Analyze the user's request and choose the template with the name that most closely matches it.
    - If the user asks for "just listed", you must choose the "Just Listed" template if it exists.
    - If no template is a clear match, choose the most generic one (like a general property ad).
    - You MUST respond with ONLY the UID of the best-matching template. Do not add any other text, explanation, or JSON formatting.
    
    Example Response:
    u123abc456def
    """
    try:
        response = llm.invoke(prompt)
        best_uid = response.content.strip()
        return next((t for t in templates if t["uid"] == best_uid), None)
    except Exception as e:
        print(f"Error during LLM template selection: {e}")
        return None

def _create_modifications_with_llm(property_data: dict, template: dict) -> List[Dict[str, Any]]:
    """Helper function to use an LLM for intelligent data mapping."""
    llm = ChatGoogleGenerativeAI(model="gemini-1.5-flash", temperature=0.0)
    # We only need to show the LLM the layers it can modify
    modifiable_layers = template.get('available_modifications', [])

    # The mapping and example are now part of the prompt for the LLM's reference
    prompt = f"""
    You are an expert data mapper for a real estate design tool. Your only job is to create a JSON list of modifications by mapping the provided PROPERTY DATA to the modifiable LAYERS of the provided TEMPLATE.

    ---
    DATA MAPPING GUIDE:
    Use this guide to understand how to map TEMPLATE layer names to the data paths in the PROPERTY DATA.
    The key is the template layer name, and the value is the dot-notation path to the data.

    {{
        "property_address": "address",
        "city": "city",
        "state": "state",
        "zip": "zip",
        "property_price": "price_display",
        "description": "description",
        "bedrooms": "bedrooms",
        "bathrooms": "bathrooms",
        "square_feet": "square_feet",
        "agent_name": "agents.listing_agent.name",
        "agent_contact": "agents.listing_agent.phone",
        "agent_email": "agents.listing_agent.email",
        "neighborhood": "geo_data.neighborhood_name",
        "brokerage_name": "agents.listing_agent.office.name",
        "property_type": "property_type",
        "property_image": "hero.large",
        "photo1": "photos[1].large",
        "photo2": "photos[2].large",
        "photo3": "photos[3].large",
        "agent_photo": null
    }}

    TASK:
    Based on the rules and data, generate the JSON list of modifications for the following request.

    PROPERTY DATA:
    {json.dumps(property_data, indent=2)}

    TEMPLATE (only modifiable layers are shown):
    {json.dumps(modifiable_layers, indent=2)}

    Instructions:
    1.  Create a JSON list of "modifications". Each modification is an object with "name" and "text" or "image_url".
    2.  Use the `DATA MAPPING GUIDE` and the live `PROPERTY DATA` to find the correct values for the layers listed in the `TEMPLATE`.
    3.  **Formatting is critical:**
        - The `price_display` field is already formatted. Use it directly for any price layer.
        - Combine `city`, `state`, and `zip` for any full address or location layer if one exists.
        - Combine `bedrooms` and `bathrooms` into a single string like "2 Beds | 2.0 Baths" if a layer like `beds_baths` exists.
    4.  For image layers (e.g., `property_image`, `photo1`), use the `DATA MAPPING GUIDE` to find the correct path in the `PROPERTY DATA` and get the image URL.
    5.  If the `PROPERTY DATA` contains extra fields provided by the user (like `open_house_date`, `open_house_time`, `custom_headline`), map them directly to the corresponding template layers.
    6.  Do not invent data. If a value for a layer isn't available in the property data, simply omit that layer from your list.
    7.  Respond ONLY with the raw JSON list. Do not add any other text, explanations, or markdown formatting like ```json.
    """
    try:
        response = llm.invoke(prompt)
        # Clean the response to ensure it's valid JSON
        cleaned_response = response.content.strip().replace("```json", "").replace("```", "")
        return json.loads(cleaned_response)
    except Exception as e:
        print(f"Error during LLM mapping: {e}")
        return []

def _get_missing_fields(template: dict, property_data: dict) -> Dict[str, str]:
    """
    Identifies required template fields that are not present in the property data.
    These are fields that typically require user input.
    Returns a dictionary mapping the field key to a user-friendly description.
    """
    # Define fields that are candidates for user input because they aren't in standard MLS data.
    potential_user_fields = {
        "open_house_date": "the date of the open house (e.g., 'Saturday, June 15th')",
        "open_house_time": "the time of the open house (e.g., '2-4 PM')",
        "custom_headline": "a custom headline for the ad",
    }
    missing_fields = {}
    # Get the names of all modifiable layers in the template
    template_layer_names = [mod['name'] for mod in template.get('available_modifications', [])]
    
    for field_key, field_description in potential_user_fields.items():
        # If a potential user field exists as a layer in the template AND is not already in our property data...
        if field_key in template_layer_names and field_key not in property_data:
            # ...then we need to ask the user for it.
            missing_fields[field_key] = field_description
            
    return missing_fields

@tool
def list_available_designs() -> Dict[str, Any]:
    """Use this tool when the user asks what designs you can create or what templates are available."""
    try:
        api_key = os.environ["BANNERBEAR_API_KEY"]
        templates = api_services.fetch_all_template_details(api_key)
        if not templates:
            return {"success": False, "error": "No design templates were found."}
        
        design_names = [t['name'] for t in templates]
        return {"success": True, "designs": design_names}
    except Exception as e:
        return {"success": False, "error": f"An API error occurred: {e}"}

class AdGeneratorInput(BaseModel):
    mls_listing_id: str = Field(description="The unique Multiple Listing Service ID for the property.")
    mls_id: str = Field(description = "3 digit ID that represents all the listings in a specific region.")
    user_intent: str = Field(description="The user's stated goal, e.g., 'a just listed ad' or 'an open house announcement'.")


@tool(args_schema=AdGeneratorInput)
def generate_marketing_image(mls_listing_id: str, mls_id: str, user_intent: str) -> Dict[str, Any]:
    """
    Call this tool to generate a marketing image. This tool will automatically fetch all necessary property details (price, address, photos, etc.) using the MLS Listing ID and MLS ID. You do not need to ask the user for this information. The tool will either generate the image directly or ask for more information (like an open house date) if the chosen template requires it.
    """
    try:
        api_key = os.environ["BANNERBEAR_API_KEY"]
        templates = api_services.fetch_all_template_details(api_key)
        property_data = api_services.fetch_realty_details(mls_listing_id, mls_id)
        

        if not templates: return {"status": "error", "message_for_user": "I couldn't find any design templates."}
        if not property_data: return {"status": "error", "message_for_user": f"I couldn't find data for MLS Listing ID {mls_listing_id} in MLS {mls_id}."}

        best_template = _choose_best_template_with_llm(user_intent, templates)
        if not best_template:
            return {"status": "error", "message_for_user": "I couldn't determine which design template to use for your request."}

        # --- NEW LOGIC: Check for missing fields that require user input ---
        missing_fields = _get_missing_fields(best_template, property_data)
        if missing_fields:
            # The agent needs a specific string to ask the user, so we construct it here.
            field_list = " and ".join(list(missing_fields.values()))
            user_message = f"To complete the '{best_template['name']}' design, I just need a bit more information: {field_list}. Can you provide that for me?"
            
            return {
                "status": "needs_info",
                "message_for_user": user_message, 
                "context": {"mls_listing_id": mls_listing_id, "mls_id": mls_id, "template_uid": best_template['uid']}
            }

        # --- If no info is missing, proceed with generation ---
        modifications = _create_modifications_with_llm(property_data, best_template)
        if not modifications: return {"status": "error", "message_for_user": "I found the data but couldn't map it to the design."}

        image_req = api_services.start_image_generation(api_key, best_template['uid'], modifications)
        if not (polling_url := image_req.get("self")): return {"status": "error", "message_for_user": "Failed to start image generation."}
        
        final_image = api_services.poll_for_image(api_key, polling_url)
        if not final_image or not (bb_url := final_image.get("image_url_png")):
            return {"status": "error", "message_for_user": "The final image rendering failed."}
            
        # permanent_url = api_services.upload_image(bb_url)
        # return {
        #     "status": "image_generated",
        #     "message_for_user": f"Using the '{best_template['name']}' template, here is the design I created for you!\n\n![Generated Ad]({permanent_url})"
        # }
        return {
            "status": "image_generated",
            "message_for_user": f"Using the '{best_template['name']}' template, here is the design I created for you!\n\n![Generated Ad]({bb_url})"
        }

    except Exception as e:
        return {"status": "error", "message_for_user": f"A critical error occurred: {e}"}

class CompleteAdInput(BaseModel):
    mls_listing_id: str = Field(description="The original MLS Listing ID of the property, retrieved from the context of the previous step.")
    mls_id: str = Field(description="The 3-digit ID for the regional MLS, retrieved from the context of the previous step.")
    template_uid: str = Field(description="The UID of the template selected in the first step, retrieved from the context.")
    user_provided_data: Dict[str, str] = Field(description="A dictionary mapping the layer names (e.g., 'open_house_date') to the information the user provided in the conversation.")

@tool(args_schema=CompleteAdInput)
def complete_marketing_image(mls_listing_id: str, mls_id: str, template_uid: str, user_provided_data: Dict[str, str]) -> Dict[str, Any]:
    """
    Use this tool to generate a marketing image AFTER you have already asked the user for missing information and they have provided it.
    This tool combines the original property data with the new user-provided details to create the final image.
    """
    try:
        api_key = os.environ["BANNERBEAR_API_KEY"]
        
        property_data = api_services.fetch_realty_details(mls_listing_id, mls_id)
        if not property_data: return {"status": "error", "message_for_user": f"I couldn't re-fetch data for MLS Listing ID {mls_listing_id}."}

        # Merge original data with new user-provided data
        merged_data = property_data.copy()
        merged_data.update(user_provided_data)

        # Fetch the specific template by its UID to get its layer info
        template = api_services.fetch_template_by_uid(api_key, template_uid)
        if not template: return {"status": "error", "message_for_user": "I couldn't re-fetch the design template."}

        modifications = _create_modifications_with_llm(merged_data, template)
        if not modifications: return {"status": "error", "message_for_user": "I found the data but struggled to map your new details to the design."}

        image_req = api_services.start_image_generation(api_key, template['uid'], modifications)
        if not (polling_url := image_req.get("self")): return {"status": "error", "message_for_user": "Failed to start the final image generation."}
        
        final_image = api_services.poll_for_image(api_key, polling_url)
        if not final_image or not (bb_url := final_image.get("image_url_png")):
            return {"status": "error", "message_for_user": "The final image rendering failed."}
            
        # permanent_url = api_services.upload_image(bb_url)
        # return {
        #     "status": "image_generated",
        #     "message_for_user": f"Perfect! Using your details with the '{template['name']}' template, here is the final design:\n\n![Generated Ad]({permanent_url})"
        # }
        return {
            "status": "image_generated",
            "message_for_user": f"Using the '{template['name']}' template, here is the design I created for you!\n\n![Generated Ad]({bb_url})"
        }
    except Exception as e:
        return {"status": "error", "message_for_user": f"A critical error occurred while finalizing your image: {e}"}
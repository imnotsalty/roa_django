import os
import json
from pydantic import BaseModel, Field
from typing import Dict, Any, List
from langchain.tools import tool
from langchain_google_genai import ChatGoogleGenerativeAI
from . import api_services # Use relative import for Django app structure

def _choose_best_template_with_llm(user_intent: str, templates: list) -> dict | None:
    llm = ChatGoogleGenerativeAI(model="gemini-1.5-flash", temperature=0.0)
    template_summaries = json.dumps([{"uid": t["uid"], "name": t["name"]} for t in templates])
    prompt = f"""
    You are an expert at understanding user intent. Your only job is to select the single best template from a list that matches the user's request.
    USER'S REQUEST: "{user_intent}"
    AVAILABLE TEMPLATES: {template_summaries}
    You MUST respond with ONLY the UID of the best-matching template.
    Example Response: u123abc456def
    """
    try:
        response = llm.invoke(prompt)
        best_uid = response.content.strip()
        return next((t for t in templates if t["uid"] == best_uid), None)
    except Exception as e:
        print(f"Error during LLM template selection: {e}")
        return None

def _create_modifications_with_llm(property_data: dict, template: dict) -> List[Dict[str, Any]]:
    llm = ChatGoogleGenerativeAI(model="gemini-1.5-flash", temperature=0.0)
    modifiable_layers = template.get('available_modifications', [])
    prompt = f"""
    You are an expert data mapper. Your only job is to create a JSON list of modifications by mapping the provided PROPERTY DATA to the LAYERS of the provided TEMPLATE.
    PROPERTY DATA: {json.dumps(property_data, indent=2)}
    TEMPLATE: {json.dumps(modifiable_layers, indent=2)}
    Instructions:
    1.  Create a JSON list of "modifications".
    2.  Match property data fields to template layer names logically.
    3.  Format `listPrice` with a dollar sign and commas.
    4.  Combine `city`, `state`, and `postalCode` for any address layer.
    5.  Combine `bedrooms` and `bathrooms` into a single string like "4 Beds | 3 Baths".
    6.  Use the first photo URL from `property_data['photos']` for any layer named `photo` or `main_image`.
    7.  Map user-provided keys like `open_house_date` to corresponding layers.
    8.  Respond ONLY with the raw JSON list.
    """
    try:
        response = llm.invoke(prompt)
        cleaned_response = response.content.strip().replace("```json", "").replace("```", "")
        return json.loads(cleaned_response)
    except Exception as e:
        print(f"Error during LLM mapping: {e}")
        return []

def _get_missing_fields(template: dict, property_data: dict) -> Dict[str, str]:
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
    mls_id: str = Field(description="The unique Multiple Listing Service ID for the property.")
    user_intent: str = Field(description="The user's stated goal, e.g., 'a just listed ad' or 'an open house announcement'.")

@tool(args_schema=AdGeneratorInput)
def generate_marketing_image(mls_id: str, user_intent: str) -> Dict[str, Any]:
    """Use this tool to start the image generation process once you have BOTH the user's intent AND the property's MLS ID."""
    try:
        api_key = os.environ["BANNERBEAR_API_KEY"]
        templates = api_services.fetch_all_template_details(api_key)
        property_data = api_services.fetch_realty_details(mls_id)
        if not templates: return {"status": "error", "message_for_user": "I couldn't find any design templates."}
        if not property_data: return {"status": "error", "message_for_user": f"I couldn't find data for MLS ID {mls_id}."}
        best_template = _choose_best_template_with_llm(user_intent, templates)
        if not best_template: return {"status": "error", "message_for_user": "I couldn't determine which template to use."}
        missing_fields = _get_missing_fields(best_template, property_data)
        if missing_fields:
            field_list = " and ".join(list(missing_fields.values()))
            user_message = f"To complete the '{best_template['name']}' design, I just need a bit more information: {field_list}. Can you provide that for me?"
            return {"status": "needs_info", "message_for_user": user_message, "context": {"mls_id": mls_id, "template_uid": best_template['uid']}}
        modifications = _create_modifications_with_llm(property_data, best_template)
        if not modifications: return {"status": "error", "message_for_user": "I found the data but couldn't map it to the design."}
        image_req = api_services.start_image_generation(api_key, best_template['uid'], modifications)
        if not (polling_url := image_req.get("self")): return {"status": "error", "message_for_user": "Failed to start image generation."}
        final_image = api_services.poll_for_image(api_key, polling_url)
        if not final_image or not (bb_url := final_image.get("image_url_png")): return {"status": "error", "message_for_user": "The final image rendering failed."}
        permanent_url = api_services.upload_image(bb_url)
        return {"status": "image_generated", "message_for_user": f"Using the '{best_template['name']}' template, here is the design I created for you!\n\n![Generated Ad]({permanent_url})"}
    except Exception as e:
        return {"status": "error", "message_for_user": f"A critical error occurred: {e}"}

class CompleteAdInput(BaseModel):
    mls_id: str = Field(description="The original MLS ID of the property, from context.")
    template_uid: str = Field(description="The UID of the template, from context.")
    user_provided_data: Dict[str, str] = Field(description="A dictionary mapping layer names to user-provided information.")

@tool(args_schema=CompleteAdInput)
def complete_marketing_image(mls_id: str, template_uid: str, user_provided_data: Dict[str, str]) -> Dict[str, Any]:
    """Use this tool AFTER asking the user for missing info. It combines original and new data to create the final image."""
    try:
        api_key = os.environ["BANNERBEAR_API_KEY"]
        property_data = api_services.fetch_realty_details(mls_id)
        if not property_data: return {"status": "error", "message_for_user": f"I couldn't re-fetch data for MLS ID {mls_id}."}
        merged_data = property_data.copy()
        merged_data.update(user_provided_data)
        template = api_services.fetch_template_by_uid(api_key, template_uid)
        if not template: return {"status": "error", "message_for_user": "I couldn't re-fetch the design template."}
        modifications = _create_modifications_with_llm(merged_data, template)
        if not modifications: return {"status": "error", "message_for_user": "I struggled to map your new details to the design."}
        image_req = api_services.start_image_generation(api_key, template['uid'], modifications)
        if not (polling_url := image_req.get("self")): return {"status": "error", "message_for_user": "Failed to start the final image generation."}
        final_image = api_services.poll_for_image(api_key, polling_url)
        if not final_image or not (bb_url := final_image.get("image_url_png")): return {"status": "error", "message_for_user": "The final image rendering failed."}
        permanent_url = api_services.upload_image(bb_url)
        return {"status": "image_generated", "message_for_user": f"Perfect! Using your details with the '{template['name']}' template, here is the final design:\n\n![Generated Ad]({permanent_url})"}
    except Exception as e:
        return {"status": "error", "message_for_user": f"A critical error occurred while finalizing your image: {e}"}
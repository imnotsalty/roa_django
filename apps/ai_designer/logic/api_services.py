import os
import requests
import time

BANNERBEAR_URL = "https://api.bannerbear.com/v2"

def fetch_all_template_details(api_key: str):
    headers = {"Authorization": f"Bearer {api_key}"}
    summary_response = requests.get(f"{BANNERBEAR_URL}/templates", headers=headers, timeout=20)
    summary_response.raise_for_status()
    summaries = summary_response.json()
    detailed_templates = []
    for summary in summaries:
        if uid := summary.get("uid"):
            try:
                detail_response = requests.get(f"{BANNERBEAR_URL}/templates/{uid}", headers=headers, timeout=15)
                detail_response.raise_for_status()
                details = detail_response.json()
                if details and details.get("available_modifications"):
                    detailed_templates.append(details)
            except requests.exceptions.RequestException as e:
                print(f"Warning: Could not fetch details for template {uid}. Skipping. Error: {e}")
                continue
    return detailed_templates

def fetch_template_by_uid(api_key: str, uid: str):
    headers = {"Authorization": f"Bearer {api_key}"}
    try:
        response = requests.get(f"{BANNERBEAR_URL}/templates/{uid}", headers=headers, timeout=15)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error: Could not fetch template details for {uid}. Error: {e}")
        return None

def fetch_realty_details(mls_listing_id: str, mls_id: str):
    endpoint = os.environ.get("REALTY_API_ENDPOINT")
    if not endpoint: raise ValueError("REALTY_API_ENDPOINT not set.")
    headers = {'Content-Type': 'application/json', 'x-tenant-code': 'ROA'}
    payload = {"size": 1, "mlses": [int(mls_id)], "mls_listings": [str(mls_listing_id)], "view": "detailed"}
    response = requests.post(endpoint, headers=headers, json=payload, timeout=20)
    response.raise_for_status()
    data = response.json()
    if data and data.get('data', {}).get('content', {}).get('listings'):
        return data['data']['content']['listings'][0]
    return None

def start_image_generation(api_key: str, template_id: str, modifications: list):
    headers = {"Authorization": f"Bearer {api_key}"}
    payload = {"template": template_id, "modifications": modifications}
    response = requests.post(f"{BANNERBEAR_URL}/images", headers=headers, json=payload, timeout=20)
    response.raise_for_status()
    return response.json()

def poll_for_image(api_key: str, polling_url: str):
    headers = {"Authorization": f"Bearer {api_key}"}
    start_time = time.time()
    while time.time() - start_time < 60:
        response = requests.get(polling_url, headers=headers, timeout=20)
        response.raise_for_status()
        image_object = response.json()
        if image_object.get('status') == 'completed':
            return image_object
        if image_object.get('status') == 'failed':
            return None
        time.sleep(2)
    return None

# def upload_image(image_url: str):
#     api_key = os.environ.get("FREEIMAGE_API_KEY")
#     if not api_key: return image_url
#     payload = {'key': api_key, 'action': 'upload', 'source': image_url, 'format': 'json'}
#     try:
#         response = requests.post("https://freeimage.host/api/1/upload", data=payload, timeout=30)
#         data = response.json()
#         return data.get("image", {}).get("url", image_url)
#     except Exception:
#         return image_url


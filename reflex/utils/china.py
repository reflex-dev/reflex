import requests


def _is_in_china():
    try:
        response = requests.get(f"http://ip-api.com/json")
        data = response.json()

        if data["status"] == "success":
            return data["country"] == "China"
        else:
            print(f"Error: {data['message']}")
            return None

    except requests.RequestException as e:
        print(f"Request error: {e}")
        return None

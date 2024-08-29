import unittest
import requests
import json

BASE_URL = "http://localhost:8000"

class TestFastAPIApp(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.headers = {"Content-Type": "application/json"}
        cls.access_token = None
        cls.register_and_login()

    @classmethod
    def register_and_login(cls):
        # Register
        data = {"username": "testuser", "password": "testpassword"}
        response = requests.post(f"{BASE_URL}/register", json=data)
        if response.status_code == 200:
            cls.access_token = response.json()["access_token"]
        else:
            # If registration fails (e.g., user already exists), try logging in
            response = requests.post(f"{BASE_URL}/token", data=data)
            if response.status_code == 200:
                cls.access_token = response.json()["access_token"]
            else:
                raise Exception("Failed to register or login")

        cls.headers["Authorization"] = f"Bearer {cls.access_token}"

    def test_01_check_auth(self):
        self.assertIsNotNone(self.access_token, "Failed to obtain access token")

    def test_02_generate_report(self):
        data = {
            "theme": "電池技術發展",
            "titles": {
                "全球電池市場概況": ["市場規模", "主要參與者"],
                "技術發展趨勢": ["鋰離子電池", "固態電池"]
            },
            "links": [
                "https://yez.one/post/batterycell",
                "https://www.thenewslens.com/article/181546"
            ],
            "openai_config": {
                "azure_key": "b071280275a248ba91504f7256bce665",
                "azure_base": "https://interactive-query.openai.azure.com/"
            }
        }

        response = requests.post(f"{BASE_URL}/generate_report", json=data, headers=self.headers)
        self.assertEqual(response.status_code, 200)
        result = response.json()
        self.assertIn("result", result)
        self.assertIn("total_time", result)

    def test_03_check_result(self):
        response = requests.get(f"{BASE_URL}/check_result", headers=self.headers)
        self.assertEqual(response.status_code, 200)
        result = response.json()
        self.assertIn("result", result)

    def test_04_get_report(self):
        response = requests.get(f"{BASE_URL}/get_report", headers=self.headers)
        self.assertEqual(response.status_code, 200)
        result = response.json()
        self.assertIn("result", result)

    def test_05_reprocess_content(self):
        data = {
            "command": "在全球電池市場概況中加入更多關於新興市場的資訊",
            "openai_config": {
                "azure_key": "b071280275a248ba91504f7256bce665",
                "azure_base": "https://interactive-query.openai.azure.com/"
            }
        }
        response = requests.post(f"{BASE_URL}/reprocess_content", json=data, headers=self.headers)
        self.assertEqual(response.status_code, 200)
        result = response.json()
        self.assertIn("result", result)
        self.assertIn("original_content", result["result"])
        self.assertIn("modified_content", result["result"])
        self.assertIn("part", result["result"])

    def test_06_save_reprocessed_content(self):
        data = {
            "part": "全球電池市場概況",
            "new_content": "這是更新後的全球電池市場概況內容。"
        }
        response = requests.post(f"{BASE_URL}/save_reprocessed_content", json=data, headers=self.headers)
        self.assertEqual(response.status_code, 200)
        result = response.json()
        self.assertIn("result", result)

    def test_07_delete_report(self):
        response = requests.delete(f"{BASE_URL}/delete_report", headers=self.headers)
        self.assertEqual(response.status_code, 200)
        result = response.json()
        self.assertIn("result", result)

    @classmethod
    def tearDownClass(cls):
        # Clean up: delete the test user if needed
        pass

if __name__ == "__main__":
    unittest.main()
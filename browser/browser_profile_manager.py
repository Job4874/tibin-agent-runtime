import os
import shutil
import re

class BrowserProfileManager:
    def __init__(self, base_dir: str, profiles_dir: str):
        self.base_dir = base_dir
        self.profiles_dir = os.path.join(base_dir, profiles_dir)
        os.makedirs(self.profiles_dir, exist_ok=True)

    def validate_profile_name(self, profile_name: str) -> bool:
        if not profile_name or ".." in profile_name:
            return False
        return bool(re.match(r"^[a-zA-Z0-9_-]+$", profile_name))

    def get_profile_path(self, profile_name: str) -> str:
        if not self.validate_profile_name(profile_name):
            raise ValueError("Invalid profile name")
        return os.path.join(self.profiles_dir, profile_name)

    def profile_exists(self, profile_name: str) -> bool:
        try:
            path = self.get_profile_path(profile_name)
            return os.path.exists(path)
        except ValueError:
            return False

    def create_profile(self, profile_name: str) -> str:
        path = self.get_profile_path(profile_name)
        os.makedirs(path, exist_ok=True)
        return path

    def delete_profile(self, profile_name: str, approval_token=None):
        if not approval_token:
            raise PermissionError("Explicit approval required to delete a browser profile.")
        path = self.get_profile_path(profile_name)
        if os.path.exists(path):
            shutil.rmtree(path)

    def list_profiles(self) -> list:
        return os.listdir(self.profiles_dir)

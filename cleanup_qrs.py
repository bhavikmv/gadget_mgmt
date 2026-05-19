import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gadget_mgmt.settings')
django.setup()

from qr_management.models import QRCode

def cleanup_empty_tokens():
    bad_qrs = QRCode.objects.filter(secure_token="")
    count = bad_qrs.count()
    if count > 0:
        print(f"Found {count} broken QRCode(s) with an empty secure_token. Deleting...")
        bad_qrs.delete()
        print("Cleanup successful!")
    else:
        print("No broken QRCode rows found. Database is clean!")

if __name__ == "__main__":
    cleanup_empty_tokens()

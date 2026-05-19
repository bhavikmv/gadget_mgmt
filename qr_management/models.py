import uuid
import qrcode
from io import BytesIO
from django.core.files import File
from django.db import models
from django.conf import settings
from gadgets.models import Request

class QRCode(models.Model):
    request = models.OneToOneField(Request, on_delete=models.CASCADE, related_name='qr_code')
    secure_token = models.CharField(max_length=64, unique=True)
    qr_image = models.ImageField(upload_to='qr_codes/')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"QR for Request #{self.request.id}"

    def generate_qr(self):
        if not self.secure_token:
            self.secure_token = uuid.uuid4().hex
        
        qr_data = f"REQ{self.request.id}_{self.secure_token}"
        qr = qrcode.QRCode(version=1, box_size=10, border=4)
        qr.add_data(qr_data)
        qr.make(fit=True)

        img = qr.make_image(fill_color="black", back_color="white")
        buffer = BytesIO()
        img.save(buffer, format="PNG")
        buffer.seek(0)
        file_name = f'qr_req_{self.request.id}_{self.secure_token[:6]}.png'
        self.qr_image.save(file_name, File(buffer), save=False)


class ScanLog(models.Model):
    SCAN_TYPES = (
        ('issue', 'Issue Gadget'),
        ('return', 'Return Gadget'),
        ('invalid', 'Invalid Scan'),
    )
    request = models.ForeignKey(Request, on_delete=models.CASCADE, related_name='scan_logs', null=True, blank=True)
    scan_type = models.CharField(max_length=20, choices=SCAN_TYPES)
    scanned_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    scanned_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.scan_type} at {self.scanned_at}"

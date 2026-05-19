import json
from datetime import date
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db import transaction
from gadgets.models import Request, Gadget
from .models import QRCode, ScanLog

def is_admin(user):
    return user.is_authenticated and user.is_staff

@user_passes_test(is_admin, login_url='/login/')
def qr_scanner_view(request):
    return render(request, 'qr_management/scanner.html')

@user_passes_test(is_admin, login_url='/login/')
def process_qr_scan(request):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Invalid method'}, status=400)
    
    try:
        data = json.loads(request.body)
        qr_data = data.get('qr_data', '')
        
        # QR data format: REQ<id>_<secure_token>
        if not qr_data.startswith('REQ') or '_' not in qr_data:
            return JsonResponse({'success': False, 'message': 'Invalid QR Code format.'})
            
        parts = qr_data[3:].split('_')
        if len(parts) != 2:
            return JsonResponse({'success': False, 'message': 'Invalid QR Code format.'})
            
        req_id, token = parts
        
        try:
            qr_obj = QRCode.objects.get(request_id=req_id, secure_token=token)
        except QRCode.DoesNotExist:
            return JsonResponse({'success': False, 'message': 'Invalid or unknown QR code.'})
            
        req = qr_obj.request
        
        with transaction.atomic():
            if req.status == 'returned' or not qr_obj.is_active:
                return JsonResponse({'success': False, 'message': 'Request Already Completed'})
                
            elif req.status in ['approved', 'ready']:
                # FIRST SCAN: Issue Gadget
                req.status = 'issued'
                req.issue_date = date.today()
                req.save(update_fields=['status', 'issue_date'])
                
                for item in req.items.all():
                    gadget = Gadget.objects.select_for_update().get(pk=item.gadget.pk)
                    gadget.reserved_quantity = max(0, gadget.reserved_quantity - item.quantity)
                    gadget.issued_quantity += item.quantity
                    gadget.save(update_fields=['reserved_quantity', 'issued_quantity'])
                    
                ScanLog.objects.create(request=req, scan_type='issue', scanned_by=request.user)
                return JsonResponse({'success': True, 'message': f'Gadgets successfully ISSUED for Request #{req.id}.', 'request_id': req.id})
                
            elif req.status == 'issued':
                # SECOND SCAN: Return Gadget
                req.status = 'returned'
                req.return_date = date.today()
                req.save(update_fields=['status', 'return_date'])
                
                for item in req.items.all():
                    gadget = Gadget.objects.select_for_update().get(pk=item.gadget.pk)
                    gadget.issued_quantity = max(0, gadget.issued_quantity - item.quantity)
                    gadget.save(update_fields=['issued_quantity'])
                    
                qr_obj.is_active = False
                qr_obj.save(update_fields=['is_active'])
                
                ScanLog.objects.create(request=req, scan_type='return', scanned_by=request.user)
                return JsonResponse({'success': True, 'message': f'Gadgets successfully RETURNED for Request #{req.id}.', 'request_id': req.id})
                
            else:
                return JsonResponse({'success': False, 'message': f'Cannot process request with status: {req.status}.'})
                
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)})

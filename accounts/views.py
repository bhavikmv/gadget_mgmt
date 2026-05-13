from django.shortcuts import render, redirect
from django.contrib.auth import login, logout
from django.contrib import messages

from .forms import StudentRegistrationForm, StudentLoginForm
from notifications.tasks import send_otp_email_task
from accounts.models import User
import random


# ─── AUTH VIEWS ───────────────────────────────────────────────────────────────

def register_view(request):
    """Student registration only. Admins cannot register here — they are
    created via `python manage.py createsuperuser` and log in using the
    shared login page."""
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        form = StudentRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            
            # Generate OTP
            otp = str(random.randint(100000, 999999))
            request.session['registration_email'] = user.email
            request.session['registration_otp'] = otp
            
            # Send OTP email
            send_otp_email_task.delay(user.email, otp)
            
            messages.info(request, 'Please verify your email address. An OTP has been sent to your email.')
            return redirect('verify_otp')
    else:
        form = StudentRegistrationForm()
    return render(request, 'accounts/register.html', {'form': form})

def verify_otp_view(request):
    """Verify the OTP sent to the user's email during registration."""
    if request.user.is_authenticated:
        return redirect('dashboard')
        
    email = request.session.get('registration_email')
    if not email:
        messages.error(request, 'No registration in progress.')
        return redirect('register')
        
    if request.method == 'POST':
        entered_otp = request.POST.get('otp')
        expected_otp = request.session.get('registration_otp')
        
        if entered_otp and entered_otp == expected_otp:
            try:
                user = User.objects.get(email=email)
                user.is_active = True
                user.save()
                login(request, user)
                
                # Clear session
                if 'registration_email' in request.session:
                    del request.session['registration_email']
                if 'registration_otp' in request.session:
                    del request.session['registration_otp']
                
                messages.success(request, f'Welcome, {user.first_name}! Your email is verified and account is active.')
                return redirect('dashboard')
            except User.DoesNotExist:
                messages.error(request, 'User not found.')
        else:
            messages.error(request, 'Invalid OTP. Please try again.')
            
    return render(request, 'accounts/verify_otp.html', {'email': email})

def resend_otp_view(request):
    """Resend the OTP to the user's email."""
    email = request.session.get('registration_email')
    if not email:
        return redirect('register')
        
    otp = str(random.randint(100000, 999999))
    request.session['registration_otp'] = otp
    send_otp_email_task.delay(email, otp)
    messages.info(request, 'A new OTP has been sent to your email.')
    return redirect('verify_otp')


def login_view(request):
    """Shared login page for both students and admins.
    After login, admins are redirected to /admin-panel/ and students to /dashboard/."""
    if request.user.is_authenticated:
        if request.user.is_staff:
            return redirect('admin_dashboard')
        return redirect('dashboard')

    if request.method == 'POST':
        form = StudentLoginForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            if user.is_staff:
                return redirect('admin_dashboard')
            return redirect('dashboard')
        else:
            messages.error(request, 'Invalid email or password.')
    else:
        form = StudentLoginForm()
    return render(request, 'accounts/login.html', {'form': form})


def logout_view(request):
    """Log out and redirect to login page."""
    logout(request)
    return redirect('login')

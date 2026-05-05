from django.shortcuts import render, redirect
from django.contrib.auth import login, logout
from django.contrib import messages

from .forms import StudentRegistrationForm, StudentLoginForm


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
            login(request, user)
            messages.success(request, f'Welcome, {user.first_name}! Your account has been created.')
            return redirect('dashboard')
    else:
        form = StudentRegistrationForm()
    return render(request, 'accounts/register.html', {'form': form})


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

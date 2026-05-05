from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from core.models import User, Student


class StudentRegistrationForm(UserCreationForm):
    """Registration form for students only. Admins are created via createsuperuser."""
    first_name = forms.CharField(max_length=50, required=True, widget=forms.TextInput(attrs={'placeholder': 'First Name'}))
    last_name = forms.CharField(max_length=50, required=True, widget=forms.TextInput(attrs={'placeholder': 'Last Name'}))
    email = forms.EmailField(required=True, widget=forms.EmailInput(attrs={'placeholder': 'Email Address'}))
    phone = forms.CharField(max_length=15, required=True, widget=forms.TextInput(attrs={'placeholder': 'Phone Number'}))
    gr_number = forms.CharField(max_length=20, required=True, widget=forms.TextInput(attrs={'placeholder': 'GR Number'}))
    password1 = forms.CharField(widget=forms.PasswordInput(attrs={'placeholder': 'Password'}))
    password2 = forms.CharField(widget=forms.PasswordInput(attrs={'placeholder': 'Confirm Password'}))

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email', 'password1', 'password2']

    def save(self, commit=True):
        user = super().save(commit=False)
        user.username = self.cleaned_data['email']
        if commit:
            user.save()
            # Create the linked student profile
            Student.objects.create(
                user=user,
                phone=self.cleaned_data['phone'],
                gr_number=self.cleaned_data['gr_number']
            )
        return user


class StudentLoginForm(AuthenticationForm):
    """Shared login form for both students and admins. Uses email as the username field."""
    username = forms.EmailField(widget=forms.EmailInput(attrs={'placeholder': 'Email Address', 'autofocus': True}))
    password = forms.CharField(widget=forms.PasswordInput(attrs={'placeholder': 'Password'}))

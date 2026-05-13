from django import forms
from django.forms import formset_factory, BaseFormSet
from datetime import date, timedelta
from .models import Category, Gadget

class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ['name', 'description']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 2}),
        }

class GadgetForm(forms.ModelForm):
    class Meta:
        model = Gadget
        fields = ['name', 'category', 'description', 'total_quantity', 'expected_return_date', 'is_active']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
            'expected_return_date': forms.DateInput(attrs={'type': 'date'}),
        }

class RequestForm(forms.Form):
    gadget = forms.ModelChoiceField(
        queryset=Gadget.objects.filter(is_active=True),
        empty_label="-- Select a Gadget --",
        widget=forms.Select(attrs={'class': 'form-control gadget-select'})
    )
    days = forms.ChoiceField(
        choices=[(i, f"{i} day{'s' if i > 1 else ''}") for i in range(1, 16)],
        widget=forms.Select(attrs={'class': 'form-control days-input'})
    )
    quantity = forms.IntegerField(
        min_value=1,
        initial=1,
        widget=forms.NumberInput(attrs={'class': 'form-control qty-input'})
    )
    join_waitlist = forms.BooleanField(
        required=False,
        label="Join waitlist if stock is unavailable",
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )

class BaseRequestFormSet(BaseFormSet):
    def clean(self):
        if any(self.errors):
            return

RequestFormSet = formset_factory(RequestForm, formset=BaseRequestFormSet, extra=1)

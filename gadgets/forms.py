from django import forms
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
        fields = ['name', 'category', 'description', 'quantity', 'is_active']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
        }

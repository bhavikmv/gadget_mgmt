from django import forms
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
        fields = ['name', 'category', 'description', 'total_quantity', 'is_active']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
        }


class RequestForm(forms.Form):
    """Single-gadget request form (simplified, no formset)."""

    gadget = forms.ModelChoiceField(
        queryset=Gadget.objects.filter(is_active=True),
        empty_label='— Select a Gadget —',
        widget=forms.Select(attrs={'class': 'form-control gadget-select', 'id': 'gadget-select'}),
    )
    days = forms.ChoiceField(
        choices=[(i, f'{i} day{"s" if i > 1 else ""}') for i in range(1, 31)],
        initial=7,
        widget=forms.Select(attrs={'class': 'form-control days-input', 'id': 'days-select'}),
    )
    quantity = forms.IntegerField(
        min_value=1,
        initial=1,
        widget=forms.NumberInput(attrs={
            'class': 'form-control qty-input',
            'id': 'qty-input',
            'min': '1',
        }),
    )
    join_waitlist = forms.BooleanField(
        required=False,
        label='Join waitlist if stock is unavailable',
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input', 'id': 'join-waitlist'}),
    )

    def clean(self):
        cleaned = super().clean()
        gadget = cleaned.get('gadget')
        quantity = cleaned.get('quantity')
        join_waitlist = cleaned.get('join_waitlist', False)

        if gadget and quantity:
            if quantity > gadget.total_quantity:
                raise forms.ValidationError(
                    f'Requested quantity ({quantity}) exceeds total stock ({gadget.total_quantity}).'
                )
        return cleaned

from django.forms import formset_factory, BaseFormSet

class BaseRequestFormSet(BaseFormSet):
    def clean(self):
        if any(self.errors):
            return

RequestFormSet = formset_factory(RequestForm, formset=BaseRequestFormSet, extra=1)



class WaitlistForm(forms.Form):
    """Minimal form for joining a waitlist directly from the gadget card."""
    gadget = forms.ModelChoiceField(queryset=Gadget.objects.filter(is_active=True))
    quantity = forms.IntegerField(min_value=1, initial=1)
    days = forms.IntegerField(min_value=1, max_value=30, initial=7)


class IssueRequestForm(forms.Form):
    """Admin form when issuing a request – allows overriding the return date."""
    expected_return_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        label='Expected Return Date',
    )
    admin_notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'rows': 2, 'class': 'form-control'}),
    )

    def clean_expected_return_date(self):
        d = self.cleaned_data.get('expected_return_date')
        if d and d < date.today():
            raise forms.ValidationError('Return date cannot be in the past.')
        return d

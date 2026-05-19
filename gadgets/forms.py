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
        fields = ['name', 'category', 'description', 'total_quantity', 'is_active', 'image']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
        }


from django.db.models import F

class GadgetChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        return f"{obj.name} (Remaining: {obj.available_quantity} / Total: {obj.total_quantity})"


class RequestForm(forms.Form):
    """Single-gadget request form (simplified, no formset)."""

    gadget = GadgetChoiceField(
        queryset=Gadget.objects.filter(is_active=True).annotate(
            calculated_available=F('total_quantity') - F('reserved_quantity') - F('issued_quantity')
        ).filter(calculated_available__gt=0),
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

    def clean(self):
        cleaned = super().clean()
        gadget = cleaned.get('gadget')
        quantity = cleaned.get('quantity')

        if gadget and quantity:
            if quantity > gadget.total_quantity:
                raise forms.ValidationError(
                    f'Quantity ({quantity}) exceeds total stock ({gadget.total_quantity}) for "{gadget.name}".'
                )
            if gadget.available_quantity < quantity:
                raise forms.ValidationError(
                    f'Not enough stock for "{gadget.name}". '
                    f'Available: {gadget.available_quantity}, you requested: {quantity}. '
                    f'Please try again when stock is replenished.'
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

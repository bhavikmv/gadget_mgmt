from django import forms
from django.forms import formset_factory, BaseFormSet
from datetime import date, timedelta
from .models import Booking
from gadgets.models import Gadget

class BookingForm(forms.Form):
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

    def clean(self):
        cleaned_data = super().clean()
        gadget = cleaned_data.get('gadget')
        days = cleaned_data.get('days')
        quantity = cleaned_data.get('quantity', 1)

        if gadget and days and quantity:
            days = int(days)
            start_date = date.today()
            end_date = start_date + timedelta(days=days - 1)

            # Individual row check (still useful for immediate feedback)
            available = gadget.available_quantity(start_date, end_date)
            if available < quantity:
                raise forms.ValidationError(
                    f"Not enough units of '{gadget.name}' available."
                )
        return cleaned_data

class BaseBookingFormSet(BaseFormSet):
    def clean(self):
        """Check total quantity across all forms for each gadget."""
        if any(self.errors):
            return

        gadget_totals = {}
        today = date.today()

        for form in self.forms:
            if self.can_delete and self._should_delete_form(form):
                continue
            
            gadget = form.cleaned_data.get('gadget')
            quantity = form.cleaned_data.get('quantity')
            days = form.cleaned_data.get('days')

            if gadget and quantity and days:
                days = int(days)
                end_date = today + timedelta(days=days - 1)
                
                # We use the gadget ID as key, but also consider the date range
                # For simplicity in this system (since all start today), we just check max duration
                # or we could group by gadget and find the max end_date.
                if gadget.id not in gadget_totals:
                    gadget_totals[gadget.id] = {
                        'gadget': gadget,
                        'total_qty': 0,
                        'max_end_date': today
                    }
                
                gadget_totals[gadget.id]['total_qty'] += quantity
                if end_date > gadget_totals[gadget.id]['max_end_date']:
                    gadget_totals[gadget.id]['max_end_date'] = end_date

        for g_id, data in gadget_totals.items():
            gadget = data['gadget']
            total_qty = data['total_qty']
            max_end_date = data['max_end_date']
            
            available = gadget.available_quantity(today, max_end_date)
            if available < total_qty:
                raise forms.ValidationError(
                    f"Total requested quantity for '{gadget.name}' is {total_qty}, but only {available} are available until {max_end_date.strftime('%d %b %Y')}."
                )

BookingFormSet = formset_factory(BookingForm, formset=BaseBookingFormSet, extra=1)

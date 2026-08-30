from django import forms

from .models import Vehicle, normalize_plate, validate_plate


class VehicleForm(forms.ModelForm):
    class Meta:
        model = Vehicle
        fields = [
            "plate",
            "brand",
            "model",
            "version",
            "model_year",
            "manufacture_year",
            "color",
            "fuel",
            "chassis",
            "notes",
        ]
        widgets = {
            "plate": forms.TextInput(
                attrs={
                    "placeholder": "ABC1D23",
                    "autocapitalize": "characters",
                    "autocomplete": "off",
                    "class": "input-plate",
                }
            ),
            "brand": forms.TextInput(attrs={"placeholder": "Chevrolet"}),
            "model": forms.TextInput(attrs={"placeholder": "Onix"}),
            "version": forms.TextInput(attrs={"placeholder": "opcional"}),
            "color": forms.TextInput(attrs={"placeholder": "Prata"}),
            "chassis": forms.TextInput(attrs={"placeholder": "opcional"}),
            "notes": forms.Textarea(attrs={"rows": 3, "placeholder": "opcional"}),
        }

    def clean_plate(self):
        plate = normalize_plate(self.cleaned_data.get("plate"))
        validate_plate(plate)

        existing = Vehicle.objects.filter(plate=plate)
        if self.instance.pk:
            existing = existing.exclude(pk=self.instance.pk)
        if existing.exists():
            raise forms.ValidationError("Já existe um veículo cadastrado com esta placa.")

        return plate

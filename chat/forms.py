from django import forms

from users.models import User

from .models import Channel, Message


class DarkStyledMixin:
    def apply_dark_styles(self):
        for field in self.fields.values():
            widget = field.widget
            existing = widget.attrs.get("class", "")
            widget.attrs["class"] = f"{existing} form-control discord-input".strip()


class ChannelForm(DarkStyledMixin, forms.ModelForm):
    class Meta:
        model = Channel
        fields = ("name", "description", "kind", "audience")
        labels = {
            "name": "Nazwa kanału",
            "description": "Opis",
            "kind": "Rodzaj kanału",
            "audience": "Dostęp kanału",
        }
        widgets = {
            "name": forms.TextInput(attrs={"placeholder": "np. ogloszenia"}),
            "description": forms.Textarea(
                attrs={"rows": 3, "placeholder": "Do czego służy ten kanał?"}
            ),
            "kind": forms.Select(),
            "audience": forms.Select(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_dark_styles()
        self.fields["kind"].widget.attrs["class"] = (
            "form-select discord-select app-select-field"
        )
        self.fields["audience"].widget.attrs["class"] = (
            "form-select discord-select app-select-field"
        )


class MessageForm(DarkStyledMixin, forms.ModelForm):
    def __init__(self, *args, **kwargs):
        self.channel = kwargs.pop("channel", None)
        self.thread = kwargs.pop("thread", None)
        super().__init__(*args, **kwargs)
        if self.channel is not None:
            self.instance.channel = self.channel
        if self.thread is not None:
            self.instance.thread = self.thread
        self.apply_dark_styles()
        self.fields["image"].widget.attrs.update(
            {
                "class": "form-control discord-input",
                "accept": "image/*",
                "id": "image-input",
            }
        )
        self.fields["voice_note"].widget.attrs.update(
            {
                "class": "form-control discord-input",
                "accept": "audio/*",
                "id": "voice-note-input",
            }
        )

    class Meta:
        model = Message
        fields = ("content", "image", "voice_note")
        labels = {
            "content": "Treść",
            "image": "Obraz",
            "voice_note": "Nagranie",
        }
        widgets = {
            "content": forms.Textarea(
                attrs={
                    "rows": 2,
                    "placeholder": "Napisz wiadomość...",
                    "id": "message-content",
                }
            ),
        }

    def clean(self):
        cleaned_data = super().clean()
        if not any(
            [
                cleaned_data.get("content"),
                cleaned_data.get("image"),
                cleaned_data.get("voice_note"),
            ]
        ):
            raise forms.ValidationError("Wiadomość musi zawierać tekst lub załącznik.")
        return cleaned_data


class ChannelMemberForm(forms.Form):
    member = forms.ModelChoiceField(
        queryset=User.objects.none(),
        label="Dodaj użytkownika",
        empty_label="Wybierz użytkownika",
        widget=forms.Select(
            attrs={"class": "form-select discord-select app-select-field"}
        ),
    )

    def __init__(self, *args, channel=None, **kwargs):
        super().__init__(*args, **kwargs)
        queryset = User.objects.order_by("username")
        if channel is not None:
            queryset = queryset.exclude(
                pk__in=channel.members.values_list("pk", flat=True)
            )
        self.fields["member"].queryset = queryset

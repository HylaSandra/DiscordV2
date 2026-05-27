from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm

from .models import User, UserReport


class StyledFormMixin:
    def apply_dark_styles(self):
        for field in self.fields.values():
            widget = field.widget
            existing = widget.attrs.get("class", "")
            widget.attrs["class"] = f"{existing} form-control discord-input".strip()


class LoginForm(StyledFormMixin, AuthenticationForm):
    username = forms.CharField(
        label="Login lub email",
        widget=forms.TextInput(
            attrs={"placeholder": "Wpisz login lub email", "autofocus": True}
        ),
    )
    password = forms.CharField(
        label="Hasło",
        strip=False,
        widget=forms.PasswordInput(attrs={"placeholder": "Wpisz hasło"}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_dark_styles()

    def confirm_login_allowed(self, user):
        super().confirm_login_allowed(user)
        if user.is_currently_blocked:
            raise forms.ValidationError(
                "To konto jest aktualnie zablokowane przez moderatora.",
                code="blocked",
            )


class RegistrationForm(StyledFormMixin, UserCreationForm):
    email = forms.EmailField(
        label="Email", widget=forms.EmailInput(attrs={"placeholder": "Wpisz email"})
    )

    class Meta:
        model = User
        fields = ("username", "email", "password1", "password2")
        labels = {
            "username": "Login",
            "password1": "Hasło",
            "password2": "Powtórz hasło",
        }
        help_texts = {
            "username": "Wymagania: maksymalnie 150 znaków. Możesz używać liter, cyfr i znaków @/./+/-/_.",
        }
        widgets = {
            "username": forms.TextInput(attrs={"placeholder": "Wpisz login"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_dark_styles()

    def clean_email(self):
        email = self.cleaned_data["email"].lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("Podany adres email jest już zajęty.")
        return email

    def clean_username(self):
        username = self.cleaned_data["username"]
        if User.objects.filter(username__iexact=username).exists():
            raise forms.ValidationError("Podany login jest już zajęty.")
        return username


class ProfileForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = User
        fields = ("avatar", "bio", "status", "email")
        labels = {
            "avatar": "Avatar",
            "bio": "Opis",
            "status": "Status",
            "email": "Email",
        }
        widgets = {
            "bio": forms.Textarea(attrs={"rows": 4, "placeholder": "Napisz coś o sobie"}),
            "status": forms.Select(),
            "email": forms.EmailInput(attrs={"placeholder": "Twój email"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_dark_styles()
        self.fields["avatar"].widget.attrs["class"] = "form-control discord-input"
        self.fields["status"].widget.attrs["class"] = (
            "form-select discord-select app-select-field"
        )

    def clean_email(self):
        email = self.cleaned_data["email"].lower()
        queryset = User.objects.filter(email__iexact=email).exclude(pk=self.instance.pk)
        if queryset.exists():
            raise forms.ValidationError("Ten email jest już przypisany do innego konta.")
        return email


class RoleUpdateForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ("role",)
        widgets = {
            "role": forms.Select(
                attrs={"class": "form-select discord-select directory-role-select"}
            ),
        }


class UserReportForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = UserReport
        fields = ("reason", "description")
        labels = {
            "reason": "Powód zgłoszenia",
            "description": "Opis sytuacji",
        }
        widgets = {
            "reason": forms.Select(),
            "description": forms.Textarea(
                attrs={
                    "rows": 5,
                    "placeholder": "Opisz, co się wydarzyło i dlaczego zgłaszasz tego użytkownika.",
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_dark_styles()
        self.fields["reason"].widget.attrs["class"] = (
            "form-select discord-select app-select-field"
        )


class UserReportReviewForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = UserReport
        fields = ("status", "moderator_note")
        labels = {
            "status": "Status",
            "moderator_note": "Notatka moderatora",
        }
        widgets = {
            "status": forms.Select(),
            "moderator_note": forms.Textarea(
                attrs={
                    "rows": 3,
                    "placeholder": "Dodaj krótką notatkę o decyzji lub dalszych krokach.",
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_dark_styles()
        self.fields["status"].widget.attrs["class"] = (
            "form-select discord-select app-select-field"
        )

from .navigation import build_navigation_context


def global_navigation(request):
    if not request.user.is_authenticated:
        return {}
    context = build_navigation_context(request.user)
    context.pop("viewer", None)
    return context

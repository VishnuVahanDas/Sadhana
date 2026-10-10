from django.shortcuts import render
from django.utils.translation import gettext_lazy as _


def placeholder(title, phase):
    """Stand-in page for a screen that a later build phase will replace."""

    def view(request):
        return render(request, "placeholder.html", {"title": title, "phase": phase})

    return view


home = placeholder(_("Today"), 2)
me = placeholder(_("My Report"), 4)
ranks = placeholder(_("Ranks"), 5)
analysis = placeholder(_("Analysis"), 5)
devotees = placeholder(_("Devotees"), 3)

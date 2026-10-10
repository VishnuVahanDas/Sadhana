from django.urls import reverse

from .test_dashboard import filled, today  # noqa: F401  (fixtures)


def page(client, person, **params):
    return client.get(reverse("dashboard", args=[person.pk]), params)


def test_heatmap_selector_swaps_its_own_section(client, filled):
    """Changing the heatmap field must not reload the page to the top (dashboard.js swaps #calendar)."""
    client.force_login(filled)
    html = page(client, filled, heat="rounds").content.decode()
    assert '<section id="calendar"' in html
    assert 'data-swap="calendar"' in html
    # Fallback without the script: a normal reload that lands back on the section.
    assert 'action="#calendar"' in html
    section = html.split('<section id="calendar"')[1].split("</section>")[0]
    assert "data-autosubmit" not in section and "data-heat" in section

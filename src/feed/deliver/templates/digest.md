# Daily Digest — {{ digest.date.strftime('%A, %B %d, %Y') }}

{{ digest.total_articles }} articles from {{ digest.total_feeds }} sources

{% if digest.overall_themes %}
## Today's Themes

{% for theme in digest.overall_themes %}- {{ theme }}
{% endfor %}
{% endif %}
{% if digest.non_obvious_insights %}
## Non-Obvious Insights

{% for insight in digest.non_obvious_insights %}- **{{ insight.insight }}**
  _Why unintuitive: {{ insight.why_unintuitive }}_
{% endfor %}
{% endif %}

{% for category in digest.categories %}
---

## {{ category.name }} ({{ category.article_count }} article{% if category.article_count != 1 %}s{% endif %})

{% if category.synthesis %}
{{ category.synthesis }}

{% endif %}
{% if category.top_takeaways %}
### Key Takeaways

{% for takeaway in category.top_takeaways[:3] %}- {{ takeaway }}
{% endfor %}
{% endif %}
{% if category.non_obvious_insight %}
### Non-Obvious Insight

- **{{ category.non_obvious_insight.insight }}**
  _Why unintuitive: {{ category.non_obvious_insight.why_unintuitive }}_

{% endif %}
{% for article in category.articles %}
#### {{ article.title }}

{{ article.author }} · {{ article.feed_name }}
{% if article.summary %}

{{ article.summary }}
{% endif %}

[Read more]({{ article.url }})

{% endfor %}
{% endfor %}
---

_Generated in {{ "%.1f"|format(digest.processing_time_seconds) }}s · Powered by Feed_

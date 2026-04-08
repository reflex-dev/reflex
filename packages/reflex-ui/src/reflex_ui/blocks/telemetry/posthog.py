"""PostHog analytics tracking integration for Reflex applications."""

import json

import reflex as rx

# PostHog tracking configuration
POSTHOG_API_HOST: str = "https://us.i.posthog.com"

# PostHog initialization script template
POSTHOG_SCRIPT_TEMPLATE: str = """
!function(t,e){{
    var o,n,p,r;
    e.__SV||(window.posthog=e,e._i=[],e.init=function(i,s,a){{
        function g(t,e){{
            var o=e.split(".");
            2==o.length&&(t=t[o[0]],e=o[1]),t[e]=function(){{
                t.push([e].concat(Array.prototype.slice.call(arguments,0)))
            }}
        }}
        (p=t.createElement("script")).type="text/javascript",p.async=!0,p.src=s.api_host.replace(".i.posthog.com","-assets.i.posthog.com")+"/static/array.js",(r=t.getElementsByTagName("script")[0]).parentNode.insertBefore(p,r);
        var u=e;
        for(void 0!==a?u=e[a]=[]:a="posthog",u.people=u.people||[],u.toString=function(t){{
            var e="posthog";
            return"posthog"!==a&&(e+="."+a),t||(e+=" (stub)"),e
        }},u.people.toString=function(){{
            return u.toString(1)+".people (stub)"
        }},o="capture identify alias people.set people.set_once set_config register register_once unregister opt_out_capturing has_opted_out_capturing opt_in_capturing reset isFeatureEnabled onFeatureFlags getFeatureFlag getFeatureFlagPayload reloadFeatureFlags group updateEarlyAccessFeatureEnrollment getEarlyAccessFeatures getActiveMatchingSurveys getSurveys getNextSurveyStep onSessionId setPersonProperties".split(" "),n=0;n<o.length;n++)g(u,o[n]);
        e._i.push([i,s,a])
    }},e.__SV=1)
}}(document,window.posthog||[]);

posthog.init('{project_id}', {{
    api_host: '{api_host}',
    person_profiles: 'always',
    session_recording: {{
        recordCrossOriginIframes: true,
    }}
}});
"""


def identify_posthog_user(user_id: str) -> rx.event.EventSpec:
    """Identify a user in PostHog analytics.

    Args:
        user_id: Unique identifier for the user

    Returns:
        rx.event.EventSpec: Event specification for identifying the user in PostHog
    """
    user_id = json.dumps(user_id)

    return rx.call_script(
        f"""
        if (typeof posthog !== 'undefined') {{
            posthog.identify({user_id});
        }}
        """
    )


def get_posthog_trackers(
    project_id: str,
    api_host: str = POSTHOG_API_HOST,
) -> rx.Component:
    """Generate PostHog tracking component for a Reflex application.

    Args:
        project_id: PostHog project ID (defaults to app's project ID)
        api_host: PostHog API host URL (defaults to US instance)

    Returns:
        rx.Component: Script component needed for PostHog tracking
    """
    return rx.script(
        POSTHOG_SCRIPT_TEMPLATE.format(
            project_id=project_id,
            api_host=api_host,
        )
    )

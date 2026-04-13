"""PostHog analytics tracking integration for Reflex applications."""

import json
from typing import Any

import reflex as rx

# PostHog tracking configuration
POSTHOG_API_HOST: str = "https://pg.reflex.dev"
POSTHOG_UI_HOST: str = "https://us.posthog.com"

# PostHog initialization script template
POSTHOG_SCRIPT_TEMPLATE: str = """
!function(t,e){{var o,n,p,r;e.__SV||(window.posthog && window.posthog.__loaded)||(window.posthog=e,e._i=[],e.init=function(i,s,a){{function g(t,e){{var o=e.split(".");2==o.length&&(t=t[o[0]],e=o[1]),t[e]=function(){{t.push([e].concat(Array.prototype.slice.call(arguments,0)))}}}}(p=t.createElement("script")).type="text/javascript",p.crossOrigin="anonymous",p.async=!0,p.src=s.api_host.replace(".i.posthog.com","-assets.i.posthog.com")+"/static/array.js",(r=t.getElementsByTagName("script")[0]).parentNode.insertBefore(p,r);var u=e;for(void 0!==a?u=e[a]=[]:a="posthog",u.people=u.people||[],u.toString=function(t){{var e="posthog";return"posthog"!==a&&(e+="."+a),t||(e+=" (stub)"),e}},u.people.toString=function(){{return u.toString(1)+".people (stub)"}},o="init Dr qr Ci Br Zr Pr capture calculateEventProperties Yr register register_once register_for_session unregister unregister_for_session Xr getFeatureFlag getFeatureFlagPayload getFeatureFlagResult isFeatureEnabled reloadFeatureFlags updateFlags updateEarlyAccessFeatureEnrollment getEarlyAccessFeatures on onFeatureFlags onSurveysLoaded onSessionId getSurveys getActiveMatchingSurveys renderSurvey displaySurvey cancelPendingSurvey canRenderSurvey canRenderSurveyAsync Jr identify setPersonProperties group resetGroups setPersonPropertiesForFlags resetPersonPropertiesForFlags setGroupPropertiesForFlags resetGroupPropertiesForFlags reset setIdentity clearIdentity get_distinct_id getGroups get_session_id get_session_replay_url alias set_config startSessionRecording stopSessionRecording sessionRecordingStarted captureException startExceptionAutocapture stopExceptionAutocapture loadToolbar get_property getSessionProperty Wr Vr createPersonProfile setInternalOrTestUser Gr Fr tn opt_in_capturing opt_out_capturing has_opted_in_capturing has_opted_out_capturing get_explicit_consent_status is_capturing clear_opt_in_out_capturing $r debug ki Ur getPageViewId captureTraceFeedback captureTraceMetric Rr".split(" "),n=0;n<o.length;n++)g(u,o[n]);e._i.push([i,s,a])}},e.__SV=1)}}(document,window.posthog||[]);
posthog.init('{project_id}', {{
    api_host: '{api_host}',
    ui_host: '{ui_host}',
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


def _track_form_posthog(
    event_name: str,
    form_data: dict[str, Any],
    allowed_keys: set[str],
) -> rx.event.EventSpec:
    """Identify the submitter and capture a form event in PostHog.

    Args:
        event_name: PostHog event name to capture.
        form_data: Submitted form fields as a string-keyed dict.
        allowed_keys: Set of keys to include from form_data.

    Returns:
        Event that runs PostHog identify and capture in the browser.
    """
    filtered = {k: v for k, v in form_data.items() if k in allowed_keys}
    props_json = json.dumps(filtered)

    return rx.call_script(
        f"""
        if (typeof posthog !== 'undefined') {{
            const props = {props_json};
            const distinctId = props.email || ('anon_' + String(Date.now()));
            posthog.identify(distinctId, {{
                email: props.email,
                first_name: props.first_name,
                last_name: props.last_name,
                job_title: props.job_title,
                company_name: props.company_name,
            }});
            posthog.capture('{event_name}', props);
        }}
        """
    )


_COMMON_KEYS = {
    "email",
    "first_name",
    "last_name",
    "job_title",
    "company_name",
    "number_of_employees",
    "how_did_you_hear_about_us",
    "internal_tools",
    "technical_level",
}


def track_demo_form_posthog_submission(form_data: dict[str, Any]) -> rx.event.EventSpec:
    """Capture a demo_request event in PostHog.

    Returns:
        Event that runs PostHog identify and capture in the browser.
    """
    return _track_form_posthog("demo_request", form_data, _COMMON_KEYS)


def track_intro_form_posthog_submission(
    form_data: dict[str, Any],
) -> rx.event.EventSpec:
    """Capture an intro_submit event in PostHog.

    Returns:
        Event that runs PostHog identify and capture in the browser.
    """
    return _track_form_posthog(
        "intro_submit", form_data, _COMMON_KEYS | {"phone_number"}
    )


def get_posthog_trackers(
    project_id: str,
    api_host: str = POSTHOG_API_HOST,
    ui_host: str = POSTHOG_UI_HOST,
) -> rx.Component:
    """Generate PostHog tracking component for a Reflex application.

    Args:
        project_id: PostHog project ID (defaults to app's project ID)
        api_host: PostHog API host URL (defaults to reverse proxy)
        ui_host: PostHog UI host URL for proper link generation

    Returns:
        rx.Component: Script component needed for PostHog tracking
    """
    return rx.script(
        POSTHOG_SCRIPT_TEMPLATE.format(
            project_id=project_id,
            api_host=api_host,
            ui_host=ui_host,
        )
    )

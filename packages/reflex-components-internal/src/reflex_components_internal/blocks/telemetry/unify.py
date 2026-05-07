"""Unify analytics tracking integration for Reflex applications."""

import reflex as rx

PIXEL_SCRIPT_UNIFY: str = """
!function(){var e=["identify","page","startAutoPage","stopAutoPage","startAutoIdentify","stopAutoIdentify"];function t(o){return Object.assign([],e.reduce(function(r,n){return r[n]=function(){return o.push([n,[].slice.call(arguments)]),o},r},{}))}window.unify||(window.unify=t(window.unify)),window.unifyBrowser||(window.unifyBrowser=t(window.unifyBrowser));var n=document.createElement("script");n.async=!0,n.setAttribute("src","https://tag.unifyintent.com/v1/XAyM6RZXJzKpWH6mKPaB5S/script.js"),n.setAttribute("data-api-key","wk_DAwnkdfG_625skePqM8NZjq7jFvo6SnWFUPH2aRth"),n.setAttribute("id","unifytag"),(document.body||document.head).appendChild(n)}();"""


def get_unify_trackers() -> rx.Component:
    """Generate specific hardcoded Unify tracking components.

    Returns:
        rx.Component: The PIXEL_SCRIPT_UNIFY script component
    """
    return rx.script(PIXEL_SCRIPT_UNIFY)

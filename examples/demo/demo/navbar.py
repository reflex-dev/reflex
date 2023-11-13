import reflex as rx


menu_item_style = {
    "color": "white",
    "width": "90%",
    "margin": "0.5em",
    "borderRadius": "0.5em",
    "margin": "0.5em",
    "cursor": "pointer",
    "transition": "background 0.3s ease-in-out",
    "background": "none",
    "_hover": {
        "background": "rgba(255, 255, 255, 0.06)",
    }
}


button_style = {
    "color": "white",
    "borderRadius": "0.5em",
    "font_weight": "bold",
    "margin": "0.5em",
    "cursor": "pointer",
    "transition": "background 0.3s ease-in-out",
    "background": "none",
    "padding_x": "0.6em",
    "padding_y": "0.3em",
    "_hover": {
        "background": "rgba(255, 255, 255, 0.09)",
    }
}


heading_style = {
    "color": "white",
    "font_weight": "bold",
    "font_size": "1.5em",
    "cursor": "pointer",
    "transition": "all .9s ease-in-out",
    "color":"white",
    "padding_x": "0.6em",
    "padding_y": "0.3em",
    "_hover": {
        "color": "rgba(255, 255, 255, 0.5)",
    },
}



def navbar():
    return rx.hstack(
        rx.text("Aleksander Petuskey", style=heading_style),
        rx.spacer(),
        rx.menu(
            rx.menu_button("Hobbies", style=button_style),
        ),    
        rx.menu(
            rx.menu_button("Work", style=button_style),
        ),    
        rx.menu(
            rx.menu_button("About", style=button_style),
            rx.menu_list(
                rx.menu_item(rx.hstack(rx.image(src="github.svg"), rx.text("Github")), style=menu_item_style),
                rx.menu_item(rx.hstack(rx.image(src="linkedin.svg"), rx.text("LinkedIn")), style=menu_item_style),
                rx.menu_divider(),
                rx.menu_item(rx.hstack(rx.image(src="email.svg"), rx.text("Contact")), style=menu_item_style),
                bg="rgba(255, 255, 255, 0.09)",
                border= "1px solid rgba(57, 55, 55, 0.3)",
                margin_top="1em",
            ),
        ),
        padding_x="1em",
        padding_y="0.5em",
        position="fixed",
        width="90%",
        top="0px",
        z_index="5",
        margin="1em",
        border_radius="1em",
        style={
            "background": "rgba(255, 255, 255, 0.06)",
            "borderRadius": "16px",
            "boxShadow": "0 4px 30px rgba(0, 0, 0, 0.1)",
            "backdropFilter": "blur(5px)",
            "WebkitBackdropFilter": "blur(5px)",  # Note the capital 'W' for the vendor prefix
            "border": "1px solid rgba(57, 55, 55, 0.3)"
        }
    )
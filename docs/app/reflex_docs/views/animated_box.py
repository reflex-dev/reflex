import reflex as rx


def typing_text_script():
    return """
        var txt = 'reflex deploy';
        var speed = 50;
        var isAnimating = false;  // Add flag to track animation state

        function typeWriter(element, i) {
            if (isAnimating) return;  // Don't start if animation is running

            if (i < txt.length) {
                element.innerHTML += txt.charAt(i);
                i++;
                setTimeout(function() { typeWriter(element, i); }, speed);
            } else {
                startDeployAnimation();
            }
        }

        function startDeployAnimation() {
            try {
                if (isAnimating) return;  // Don't start if animation is running
                isAnimating = true;  // Set flag when animation starts

                // Hide typing cursor and show "Deploying..."
                document.querySelector('.typing-square').classList.replace('opacity-100', 'opacity-0');
                document.querySelector('.terminal-box').classList.add('expanded-height');
                document.querySelector('.deploying-text').classList.replace('hidden', 'flex');

                // After 800ms, collapse terminal and show deploy box
                setTimeout(function() {
                    try {
                        document.querySelector('.terminal-box').classList.add('collapsed');
                        document.querySelector('.deploy-box').classList.add('expanded');

                        // After 2.5s, switch badge from loading to ready
                        setTimeout(function() {
                            try {
                                document.querySelector('.loading-badge').classList.add('hidden');
                                document.querySelector('.ready-badge').classList.remove('hidden', 'opacity-0');

                                // After 3s with "Ready" showing, start unexpanding deploy box and reset terminal simultaneously
                                setTimeout(function() {
                                    try {
                                        document.querySelectorAll('.reflex-deploy').forEach(function(element) {
                                            element.innerHTML = '';
                                        });
                                        document.querySelector('.deploy-box').classList.remove('expanded');
                                        document.querySelector('.terminal-box').classList.remove('expanded-height', 'collapsed');
                                        document.querySelector('.deploying-text').classList.replace('flex', 'hidden');
                                        document.querySelector('.typing-square').classList.replace('opacity-0', 'opacity-100');

                                        // Reset badge after deploy box transition
                                        setTimeout(function() {
                                            try {
                                                resetBadge();
                                            } catch (error) {
                                                isAnimating = false;  // Reset flag on error
                                            }
                                        }, 550);

                                        // Wait for transitions to complete + extra delay before starting new typing
                                        setTimeout(function() {
                                            try {
                                                isAnimating = false;  // Reset flag when animation completes
                                                document.querySelectorAll('.reflex-deploy').forEach(function(element) {
                                                    typeWriter(element, 0);
                                                });
                                            } catch (error) {
                                                isAnimating = false;  // Reset flag on error
                                            }
                                        }, 1500);
                                    } catch (error) {
                                        isAnimating = false;  // Reset flag on error
                                    }
                                }, 3000);
                            } catch (error) {
                                isAnimating = false;  // Reset flag on error
                            }
                        }, 2500);
                    } catch (error) {
                        isAnimating = false;  // Reset flag on error
                    }
                }, 800);
            } catch (error) {
                isAnimating = false;  // Reset flag on error
            }
        }

        function resetBadge() {
            document.querySelector('.ready-badge').classList.add('hidden', 'opacity-0');
            document.querySelector('.loading-badge').classList.remove('hidden');
        }

        // Check if required elements exist before starting animation
        function checkElementsExist() {
            return document.querySelector('.typing-square') &&
                   document.querySelector('.terminal-box') &&
                   document.querySelector('.deploying-text') &&
                   document.querySelector('.deploy-box') &&
                   document.querySelector('.loading-badge') &&
                   document.querySelector('.ready-badge');
        }

        // Only start initial animation if elements exist and animation is not running
        function startInitialAnimation() {
            if (!checkElementsExist()) {
                setTimeout(startInitialAnimation, 100);  // Check again in 100ms
                return;
            }

            if (!isAnimating) {
                document.querySelectorAll('.reflex-deploy').forEach(function(element) {
                    typeWriter(element, 0);
                });
            }
        }

        // Start checking for elements after a 1 second delay
        setTimeout(startInitialAnimation, 1000);
    """


def status_badge(icon: str, text: str, class_name: str = ""):
    return rx.box(
        # rx.icon(tag=icon, size=10, class_name="!text-[var(--amber-8)] animate-spin"),
        (
            rx.html(
                """
            <svg xmlns="http://www.w3.org/2000/svg" width="10" height="10" viewBox="0 0 10 10" fill="none">
<g clip-path="url(#clip0_12868_454)">
<path opacity="0.2" d="M9.16255 4.99688C9.16255 5.54391 9.0548 6.08559 8.84546 6.59099C8.63612 7.09639 8.32928 7.5556 7.94247 7.94242C7.55565 8.32923 7.09644 8.63607 6.59104 8.84541C6.08564 9.05475 5.54396 9.1625 4.99692 9.1625C4.44989 9.1625 3.9082 9.05475 3.40281 8.84541C2.89741 8.63607 2.4382 8.32923 2.05138 7.94242C1.66457 7.5556 1.35773 7.09639 1.14839 6.59099C0.939046 6.08559 0.831299 5.54391 0.831299 4.99687C0.831299 4.44984 0.939046 3.90816 1.14839 3.40276C1.35773 2.89736 1.66457 2.43815 2.05138 2.05133C2.4382 1.66452 2.89741 1.35768 3.40281 1.14834C3.90821 0.938997 4.44989 0.83125 4.99692 0.83125C5.54396 0.83125 6.08564 0.938997 6.59104 1.14834C7.09644 1.35768 7.55565 1.66452 7.94247 2.05133C8.32928 2.43815 8.63612 2.89736 8.84546 3.40276C9.0548 3.90816 9.16255 4.44984 9.16255 4.99688L9.16255 4.99688Z" stroke="#E2A336" stroke-width="1.5"/>
<path d="M8.38274 7.42354C7.9312 8.05355 7.31283 8.54509 6.59719 8.84286C5.88155 9.14063 5.09702 9.23282 4.33185 9.10907C3.56667 8.98531 2.8512 8.65052 2.26591 8.14235C1.68061 7.63417 1.24872 6.97277 1.01879 6.23254C0.788862 5.49231 0.770028 4.70261 0.964405 3.95226C1.15878 3.20191 1.55866 2.52067 2.11906 1.98518C2.67946 1.44968 3.37816 1.08116 4.13657 0.921067C4.89497 0.760976 5.683 0.815663 6.41203 1.07898" stroke="#E2A336" stroke-width="1.5"/>
</g>
<defs>
<clipPath id="clip0_12868_454">
<rect width="10" height="10" fill="white"/>
</clipPath>
</defs>
</svg>
            """,
                class_name="animate-spin w-4 h-4 p-[0.1875rem] flex-shrink-0",
            )
            if icon == "loader-circle"
            else rx.html(
                """
               <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 16 16" fill="none">
<circle cx="8" cy="8" r="4" fill="#56BA9F"/>
</svg>
                """,
                class_name="h-4 w-4 shrink-0",
            )
        ),
        rx.text(text, class_name="text-xs font-medium text-secondary-11"),
        class_name=f"flex h-5 p-[0rem_0.375rem_0rem_0.125rem] items-center gap-0.5 rounded-[0.375rem] border border-slate-5 bg-slate-1 {class_name}",
    )


def purple_gradient_circle():
    return rx.box(
        class_name="w-80 h-80 flex-shrink-0 rounded-[20rem] bg-[radial-gradient(50%_50%_at_50%_50%,_var(--c-violet-3)_0%,_rgba(26,27,29,0.00)_100%)] absolute bottom-[-15.5rem] left-1/2 transform -translate-x-1/2 z-[-1]",
    )


def terminal_box():
    return rx.box(
        rx.el.style(
            """
            .terminal-box.collapsed {
                transform: translateY(-16px) scale(0.75);
            }

            .terminal-box.expanded-height {
                height: 6rem;
            }
            .deploy-box.expanded {
                transform: scale(1);
                bottom: 0px;
            }
            .deploy-box {
                transform: scale(0.75);
            }
            .deploy-box {
                bottom: -200px;
            }
            .typing-square.collapsed {
                opacity: 0;
            }
            """
        ),
        rx.box(
            # Ellipsis
            rx.box(
                rx.box(class_name="w-2 h-2 rounded-full bg-[var(--red-9)]"),
                rx.box(class_name="w-2 h-2 rounded-full bg-[var(--amber-9)]"),
                rx.box(class_name="w-2 h-2 rounded-full bg-[var(--green-9)]"),
                class_name="flex flex-row gap-1 items-center",
            ),
            # Terminal text
            rx.text(
                "terminal",
                class_name="text-secondary-11 text-xs font-medium text-center leading-4",
            ),
            class_name="flex p-[0.25rem_8.5rem_0.25rem_0.5rem] items-center gap-[6.0625rem] self-stretch",
        ),
        # Typing
        rx.box(
            rx.text(
                "$",
                class_name="text-slate-9 text-xs font-medium text-center leading-4 font-['JetBrains_Mono'] mr-4 self-baseline",
            ),
            rx.box(
                rx.box(
                    rx.text(
                        "",
                        class_name="text-slate-12 text-xs font-medium text-center leading-4 font-['JetBrains_Mono'] reflex-deploy mr-0.5",
                    ),
                    # Square
                    rx.box(
                        class_name="w-2 h-4 border-2 border-slate-9 typing-square opacity-100 transition-all duration-200 ease-out"
                    ),
                    class_name="flex flex-row",
                ),
                rx.text(
                    "Deploying...",
                    class_name="text-slate-9 text-xs font-medium text-center leading-4 font-['JetBrains_Mono'] deploying-text self-start hidden",
                ),
                class_name="flex flex-col",
            ),
            class_name="flex items-center p-5",
        ),
        purple_gradient_circle(),
        class_name="flex w-[20rem] h-[5rem] flex-col flex-shrink-0 rounded-xl rounded-b-none border-t-[1px] border-r-[1px] border-l-[1px] border-slate-4 bg-[light-dark(rgba(249, 249, 251, 0.48), rgba(26,27,29,0.48))] backdrop-filter backdrop-blur-[10px] terminal-box transition-all duration-[550ms] ease-in-out z-[5] origin-bottom translate-y-0 absolute bottom-0 overflow-hidden",
    )


def deploy_box():
    return rx.box(
        rx.box(
            # Gradient circle
            rx.box(
                class_name="rounded-full h-8 w-8 mr-4 shrink-0",
                style={
                    "background": "linear-gradient(180deg, #6056CF 0%, #48ACE5 100%)"
                },
            ),
            rx.box(
                rx.text("My App", class_name="text-sm font-medium text-slate-12"),
                rx.text(
                    "my-app.reflex.run",
                    class_name="text-sm font-medium text-slate-9",
                ),
                class_name="flex flex-col",
            ),
            rx.box(class_name="flex-1"),
            # Purple gradient circle
            status_badge(
                icon="loader-circle",
                text="Deploying",
                class_name="loading-badge transition-all duration-200 ease-out",
            ),
            status_badge(
                icon="ready",
                text="Ready",
                class_name="ready-badge hidden opacity-0 transition-all duration-200 ease-out",
            ),
            class_name="flex flex-row relative items-center w-full",
        ),
        purple_gradient_circle(),
        class_name="flex w-[20rem] h-[4.5rem] flex-row flex-shrink-0 rounded-xl rounded-b-none border-t-[1px] border-r-[1px] border-l-[1px] border-slate-4 bg-[light-dark(rgba(249, 249, 251, 0.48), rgba(26,27,29,0.48))] backdrop-filter backdrop-blur-[10px] deploy-box transition-all duration-[550ms] ease-in-out z-[6] origin-bottom absolute items-center p-[1rem_1.625rem_1rem_1.25rem] overflow-hidden",
    )


def animated_box(relative: bool = False) -> rx.Component:
    return rx.box(
        rx.box(
            terminal_box(),
            deploy_box(),
            # Glow
            rx.html(
                """
                <svg width="426" height="272" viewBox="0 0 426 272" fill="none" xmlns="http://www.w3.org/2000/svg">
                    <ellipse cx="213" cy="136" rx="213" ry="136" fill="url(#paint0_radial_12785_6973)"/>
                    <defs>
                        <radialGradient id="paint0_radial_12785_6973" cx="0" cy="0" r="1" gradientUnits="userSpaceOnUse" gradientTransform="translate(213 136) rotate(90) scale(136 213)">
                            <stop stop-color="var(--violet-3)"/>
                            <stop offset="1" stop-color="var(--slate-1)" stop-opacity="0"/>
                        </radialGradient>
                    </defs>
                </svg>
                """,
                class_name="absolute bottom-[-6.5rem] left-1/2 transform -translate-x-1/2 w-[26.625rem] h-[17rem] flex-shrink-0 pointer-events-none",
            ),
            class_name="justify-center flex flex-col items-center max-w-[34.5rem] max-h-[17.875rem] shrink-0 relative w-full h-full overflow-hidden",
        ),
        on_mount=rx.call_script(typing_text_script()),  # On dev it will run twice
        class_name="flex items-center justify-center  w-[34.5rem] h-[5rem]"
        if relative
        else "flex items-center justify-center  w-[34.5rem] h-[17.875rem] top-[13rem] absolute",
    )

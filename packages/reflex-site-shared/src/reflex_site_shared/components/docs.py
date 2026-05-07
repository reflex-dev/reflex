"""Template for documentation pages."""

from .blocks import *


def right_sidebar_item_highlight():
    """Right sidebar item highlight.

    Returns:
        The component.
    """
    return r"""
   function setupTableOfContentsHighlight() {
    // Delay to ensure DOM is fully loaded
    setTimeout(() => {
        const tocLinks = document.querySelectorAll('#toc-navigation a');
        const activeClasses = [
            'text-primary-9',
            'dark:text-primary-11',
            'shadow-[1.5px_0_0_0_var(--primary-11)_inset]',
            'dark:shadow-[1.5px_0_0_0_var(--primary-9)_inset]',
        ];
        const defaultClasses = ['text-m-slate-7', 'dark:text-m-slate-6'];

        function normalizeId(id) {
            return id.toLowerCase().replace(/\s+/g, '-');
        }

        function setDefaultState(link) {
            activeClasses.forEach(cls => link.classList.remove(cls));
            defaultClasses.forEach(cls => link.classList.add(cls));
        }

        function setActiveState(link) {
            defaultClasses.forEach(cls => link.classList.remove(cls));
            activeClasses.forEach(cls => link.classList.add(cls));
        }

        function highlightTocLink() {
            // Get the current hash from the URL
            const currentHash = window.location.hash.substring(1);

            // Reset all links
            tocLinks.forEach(link => setDefaultState(link));

            // If there's a hash, find and highlight the corresponding link
            if (currentHash) {
                const correspondingLink = Array.from(tocLinks).find(link => {
                    // Extract the ID from the link's href
                    const linkHash = new URL(link.href).hash.substring(1);
                    return normalizeId(linkHash) === normalizeId(currentHash);
                });

                if (correspondingLink) {
                    setActiveState(correspondingLink);
                }
            }
        }

        // Add click event listeners to TOC links to force highlight
        tocLinks.forEach(link => {
            link.addEventListener('click', (e) => {
                // Remove active class from all links
                tocLinks.forEach(otherLink => setDefaultState(otherLink));

                // Add active class to clicked link
                setActiveState(e.target);
            });
        });

        // Intersection Observer for scroll-based highlighting
        const observerOptions = {
            root: null,
            rootMargin: '-20% 0px -70% 0px',
            threshold: 0
        };

        const observer = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    const headerId = entry.target.id;

                    // Find corresponding TOC link
                    const correspondingLink = Array.from(tocLinks).find(link => {
                        const linkHash = new URL(link.href).hash.substring(1);
                        return normalizeId(linkHash) === normalizeId(headerId);
                    });

                    if (correspondingLink) {
                        // Reset all links
                        tocLinks.forEach(link => setDefaultState(link));

                        // Highlight current link
                        setActiveState(correspondingLink);
                    }
                }
            });
        }, observerOptions);

        // Observe headers
        const headerSelectors = Array.from(tocLinks).map(link =>
            new URL(link.href).hash.substring(1)
        );

        headerSelectors.forEach(selector => {
            const header = document.getElementById(selector);
            if (header) {
                observer.observe(header);
            }
        });

        // Initial highlighting
        highlightTocLink();

        // Handle hash changes
        window.addEventListener('hashchange', highlightTocLink);
    }, 100);
}

// Run the function when the page loads
setupTableOfContentsHighlight();
    """

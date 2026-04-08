"""Docpage utilities: TOC generation and sidebar highlight."""

import flexdown
import mistletoe


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


def get_headings(comp: mistletoe.block_token.BlockToken):
    """Get the strings from markdown component.

    Returns:
        The component.
    """
    if isinstance(comp, mistletoe.block_token.Heading):
        heading_text = "".join(
            token.content for token in comp.children if hasattr(token, "content")
        )
        return [(comp.level, heading_text)]

    if not hasattr(comp, "children") or comp.children is None:
        return []

    headings = []
    for child in comp.children:
        headings.extend(get_headings(child))
    return headings


def get_toc(source: flexdown.Document, href: str, component_list: list | None = None):
    """Get toc.

    Returns:
        The component.
    """
    from reflex_ui_shared.components.blocks.flexdown import xd
    from reflex_ui_shared.constants import REFLEX_ASSETS_CDN

    component_list = component_list or []
    component_list = component_list[1:]

    env = source.metadata
    env["__xd"] = xd
    env["REFLEX_ASSETS_CDN"] = REFLEX_ASSETS_CDN

    doc_content = source.content
    blocks = xd.get_blocks(doc_content, href)

    content_pieces = []
    for block in blocks:
        if (
            not isinstance(block, flexdown.blocks.MarkdownBlock)
            or len(block.lines) == 0
            or not block.lines[0].startswith("#")
        ):
            continue
        content = block.get_content(env)
        content_pieces.append(content)

    content = "\n".join(content_pieces)
    doc = mistletoe.Document(content)

    headings = get_headings(doc)

    if len(component_list):
        headings.append((1, "API Reference"))
    for component_tuple in component_list:
        headings.append((2, component_tuple[1]))
    return headings, doc_content

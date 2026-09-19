Keep app wraps registered below the "Built with Reflex" badge in the rendered
page. In production builds with the badge on, the badge swallowed every
lower-priority app wrap, so `rx.data_editor`'s `<div id="portal" />` never
reached the DOM and its overlay cell editors — including the new image preview —
could not open.

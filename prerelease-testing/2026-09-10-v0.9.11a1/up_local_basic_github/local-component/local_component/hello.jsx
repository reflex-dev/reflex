/**
 * This is an example inline React component that demonstrates how to pass a subset of props
 * to the top-level `div` element.
 * 
 * This component also demonstrates how to use `useMemo` to memoize the message
 * string, and an event handler that updates a state variable when the user
 * right-clicks on the component.
 */
import React, { useMemo, useState } from 'react';

// React.forwardRef is used to allow the parent component to pass a ref to this component.
export const Hello = React.forwardRef((props, ref) => {
  // Extract the `name` prop that we care about, and pass any other props directly to the top `div`.
  const {name, ...divProps} = props;

  // This state variable controls whether the message will be all caps.
  const [cap, setCap] = useState(false);

  // Memoize the message to avoid re-calculating it on every render. Only re-calculate
  // when `cap` or `name` changes.
  const message = useMemo(() => {
    const message = `Hello${name ? ` ${name}` : ""}!`;
    return cap ? message.toUpperCase() : message;
  }, [cap, name])

  return (
    // Pass ref and remaining props to the top-level `div`.
    <div ref={ref} {...divProps}>
      <h1 onContextMenu={(e) => {e.preventDefault(); setCap((cap) => !cap)}}>
        {message}
      </h1>
    </div>
  )
})
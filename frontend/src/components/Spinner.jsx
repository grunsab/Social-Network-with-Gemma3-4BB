import React from 'react';
import './Spinner.css'; // Import the CSS for the spinner

/**
 * A simple loading spinner component.
 * @param {boolean} inline - If true, renders a smaller spinner suitable for inline use (e.g., in buttons).
 * @param {boolean} contained - If true, wraps the spinner in a centered container div.
 */
function Spinner({ inline = false, contained = false }) {
  const spinnerClass = inline ? 'spinner spinner-inline' : 'spinner';

  if (contained) {
    return (
      <div className="spinner-container">
        <span className={spinnerClass}></span>
      </div>
    );
  }

  return <span className={spinnerClass}></span>;
}

export default Spinner; 
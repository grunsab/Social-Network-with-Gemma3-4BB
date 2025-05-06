import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import Spinner from './Spinner';
import './Spinner.css'; // Import CSS to potentially catch issues if styles affect rendering/selection

describe('Spinner Component', () => {

  it('renders default spinner (not inline, not contained)', () => {
    const { container } = render(<Spinner />);
    const spinnerElement = container.querySelector('span.spinner');
    expect(spinnerElement).toBeInTheDocument();
    // Check it does NOT have the inline class
    expect(spinnerElement).not.toHaveClass('spinner-inline');
    // Check it is NOT wrapped in the container
    expect(container.querySelector('.spinner-container')).not.toBeInTheDocument();
  });

  it('renders inline spinner when inline={true}', () => {
    const { container } = render(<Spinner inline={true} />);
    const spinnerElement = container.querySelector('span.spinner');
    expect(spinnerElement).toBeInTheDocument();
    // Check it HAS the inline class
    expect(spinnerElement).toHaveClass('spinner-inline');
    // Check it is NOT wrapped in the container
    expect(container.querySelector('.spinner-container')).not.toBeInTheDocument();
  });

  it('renders contained spinner when contained={true}', () => {
    const { container } = render(<Spinner contained={true} />);
    // Check the container exists
    const containerDiv = container.querySelector('.spinner-container');
    expect(containerDiv).toBeInTheDocument();
    // Check the spinner span is inside the container
    const spinnerElement = containerDiv.querySelector('span.spinner');
    expect(spinnerElement).toBeInTheDocument();
    // Default contained spinner should not be inline
    expect(spinnerElement).not.toHaveClass('spinner-inline');
  });

  it('renders contained and inline spinner when both props are true', () => {
    const { container } = render(<Spinner inline={true} contained={true} />);
    // Check the container exists
    const containerDiv = container.querySelector('.spinner-container');
    expect(containerDiv).toBeInTheDocument();
    // Check the spinner span is inside the container
    const spinnerElement = containerDiv.querySelector('span.spinner');
    expect(spinnerElement).toBeInTheDocument();
    // Check it HAS the inline class
    expect(spinnerElement).toHaveClass('spinner-inline');
  });

}); 
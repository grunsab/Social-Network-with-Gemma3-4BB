import { useState, useCallback, useRef, useEffect } from 'react';

// Basic debounce function (can be moved to a shared utils file later)
function debounce(func, wait) {
  let timeout;
  const debounced = function executedFunction(...args) {
    const later = () => {
      clearTimeout(timeout);
      func(...args);
    };
    clearTimeout(timeout);
    timeout = setTimeout(later, wait);
  };
  // Add a cancel method to the debounced function
  debounced.cancel = () => {
    clearTimeout(timeout);
  };
  return debounced;
}

export function useAmpersoundAutocomplete(textareaRef) {
  const [suggestions, setSuggestions] = useState([]);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [loadingSuggestions, setLoadingSuggestions] = useState(false);
  const suggestionsRef = useRef(null); // Ref for suggestions container
  const interactingWithSuggestionsRef = useRef(false); // New ref to track interaction

  // Debounced fetch function
  const debouncedFetchSuggestions = useCallback(
    debounce(async (searchTerm) => {
      console.log("[AmpersoundAutocomplete] Debounced fetch triggered with searchTerm:", searchTerm);
      if (!searchTerm) {
        setSuggestions([]);
        setShowSuggestions(false);
        setLoadingSuggestions(false);
        return;
      }
      setLoadingSuggestions(true);
      try {
        const response = await fetch(`/api/v1/ampersounds/search?q=${encodeURIComponent(searchTerm)}&limit=5`, {
             credentials: 'include'
        });
        console.log("[AmpersoundAutocomplete] Fetch response status:", response.status, "ok:", response.ok);
        if (!response.ok) {
            throw new Error(`Failed to fetch suggestions, status: ${response.status}`);
        }
        const data = await response.json();
        console.log("[AmpersoundAutocomplete] Fetched data:", data);
        setSuggestions(data || []);
        const shouldShow = (data || []).length > 0;
        setShowSuggestions(shouldShow); 
        console.log("[AmpersoundAutocomplete] Set suggestions:", data || [], "Set showSuggestions:", shouldShow);
      } catch (err) {
        console.error("[AmpersoundAutocomplete] Error fetching ampersound suggestions:", err);
        setSuggestions([]);
        setShowSuggestions(false);
      } finally {
          setLoadingSuggestions(false);
      }
    }, 300), // 300ms debounce delay
    [] // Empty dependency array for useCallback
  );

  const handleContentChange = useCallback((event, currentContentSetter) => {
    const newValue = event.target.value;
    currentContentSetter(newValue); // Update the component's state

    const cursorPos = event.target.selectionStart;
    const textBeforeCursor = newValue.substring(0, cursorPos);
    const match = textBeforeCursor.match(/&([a-zA-Z0-9_.-]*)$/); 

    if (match) {
        const searchTerm = match[1]; 
        debouncedFetchSuggestions(searchTerm);
    } else {
        setShowSuggestions(false); 
        setSuggestions([]);
        debouncedFetchSuggestions.cancel(); // Cancel pending fetch
    }
  }, [debouncedFetchSuggestions]);

  const handleSuggestionClick = useCallback((tag, currentContent, currentContentSetter) => {
    const cursorPos = textareaRef.current?.selectionStart;
    if (cursorPos === undefined || cursorPos === null) return;

    const textBeforeCursor = currentContent.substring(0, cursorPos);
    const lastAmpersandIndex = textBeforeCursor.lastIndexOf('&');
    if (lastAmpersandIndex === -1) return; 

    const textBeforeTag = currentContent.substring(0, lastAmpersandIndex);
    const textAfterCursor = currentContent.substring(cursorPos);
    const newContent = `${textBeforeTag}${tag} ${textAfterCursor}`; 

    currentContentSetter(newContent);
    setShowSuggestions(false);
    setSuggestions([]);
    debouncedFetchSuggestions.cancel(); // Cancel any pending fetch

    setTimeout(() => {
        const newCursorPos = lastAmpersandIndex + tag.length + 1; 
        textareaRef.current?.focus();
        textareaRef.current?.setSelectionRange(newCursorPos, newCursorPos);
    }, 0);
  }, [textareaRef, debouncedFetchSuggestions]);

  // Effect for closing suggestions when clicking outside
  useEffect(() => {
    const handleClickOutside = (event) => {
        // Close if click is outside the suggestions box AND outside the textarea
        if (suggestionsRef.current && !suggestionsRef.current.contains(event.target) && 
            textareaRef.current && !textareaRef.current.contains(event.target)) 
        {
            setShowSuggestions(false);
        }
    };
    if (showSuggestions) { // Only add listener when suggestions are shown
        document.addEventListener("mousedown", handleClickOutside);
    }
    return () => {
        document.removeEventListener("mousedown", handleClickOutside);
    };
  }, [showSuggestions, textareaRef]); // Depend on showSuggestions and the textarea ref

  // Function to manually hide suggestions (e.g., on blur or submit)
  const hideSuggestions = useCallback(() => {
      // If the user is currently interacting (mouse down) with the suggestions list,
      // don't hide it. This allows clicks on buttons within the list (like preview)
      // without closing the list due to the textarea blurring.
      if (interactingWithSuggestionsRef.current) {
          return;
      }
      setShowSuggestions(false);
      debouncedFetchSuggestions.cancel();
  }, [debouncedFetchSuggestions]);

  // Attach mouse down/up listeners to the suggestions list itself
  // This is necessary so the component using the hook can spread these props
  // onto the suggestions ul element.
  const suggestionListProps = {
    ref: suggestionsRef,
    onMouseDown: () => {
      interactingWithSuggestionsRef.current = true;
    },
    onMouseUp: () => {
      interactingWithSuggestionsRef.current = false;
    },
    // Optional: onMouseLeave might be useful in some cases,
    // but onMouseUp should cover most scenarios.
    // onMouseLeave: () => {
    //   interactingWithSuggestionsRef.current = false;
    // }
  };

  return {
    suggestions,
    showSuggestions,
    loadingSuggestions,
    suggestionListProps, // Pass these props to be spread on the UL
    handleContentChange, // Let the component call this on textarea change
    handleSuggestionClick, // Let the component call this when a suggestion LI is clicked
    hideSuggestions // Function to manually hide
  };
} 
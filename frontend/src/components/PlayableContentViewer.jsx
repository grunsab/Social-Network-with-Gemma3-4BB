import React, { useEffect, useRef, useState } from 'react';

const PlayableContentViewer = ({ htmlContent }) => {
    const contentRef = useRef(null);
    const [activeAudio, setActiveAudio] = useState(null);
    const [error, setError] = useState(null);
    const audioCacheRef = useRef(new Map());

    console.log('[DEBUG PlayableContentViewer] Initial htmlContent prop:', htmlContent);

    // Pre-process htmlContent to create clickable ampersound spans
    let processedHtmlContent = htmlContent || ''; // Ensure it's not null/undefined

    // Step 1: Standardize &amp; to & for ampersound patterns
    console.log('[DEBUG PlayableContentViewer] Before Step 1 processing:', processedHtmlContent);
    
    // OLD Step 1 regex: /&amp;(?=([a-zA-Z0-9_.-]+)\.([a-zA-Z0-9_.-]+))/g
    // In OLD version, callback args were (match, usernameFromLookahead, soundnameFromLookahead) where match was just "&amp;"

    // NEW Step 1 regex: Matches "&amp;username.soundname" directly
    processedHtmlContent = processedHtmlContent.replace(/&amp;([a-zA-Z0-9_.-]+)\.([a-zA-Z0-9_.-]+)/g, (fullMatchedString, capturedUsername, capturedSoundname) => {
        console.log(`[DEBUG PlayableContentViewer] Step 1: fullMatchedString='${fullMatchedString}', capturedUsername='${capturedUsername}', capturedSoundname='${capturedSoundname}'`);
        const replacement = `&${capturedUsername}.${capturedSoundname}`;
        console.log(`[DEBUG PlayableContentViewer] Step 1: replacing with='${replacement}'`);
        return replacement;
    });
    
    console.log('[DEBUG PlayableContentViewer] After Step 1 processing:', processedHtmlContent);

    // Step 2: Replace &username.soundname with a span
    // Regex to find &username.soundname
    // Assumes username and soundname consist of alphanumeric characters, underscores, hyphens, and dots.
    const ampersoundRegex = /&([a-zA-Z0-9_.-]+)\.([a-zA-Z0-9_.-]+)/g;
    
    processedHtmlContent = processedHtmlContent.replace(ampersoundRegex, (match, username, soundname) => {
        console.log(`[DEBUG PlayableContentViewer] Step 2: match='${match}', username='${username}', soundname='${soundname}'`);
        return `<span class="ampersound-tag" data-username="${username}" data-soundname="${soundname}" style="cursor: pointer; color: #007bff; text-decoration: underline;" role="button" tabindex="0" aria-label="Play sound ${soundname} by ${username}">${match}</span>`;
    });

    console.log('[DEBUG PlayableContentViewer] After Step 2 processing (final for render):', processedHtmlContent);

    // Cleanup previous audio element if a new one starts playing or component unmounts
    useEffect(() => {
        return () => {
            if (activeAudio) {
                activeAudio.pause();
                activeAudio.removeAttribute('src'); // Release the audio file
                activeAudio.load(); // Ensure it stops loading/buffering
            }
        };
    }, [activeAudio]); // Effect runs when activeAudio changes

    useEffect(() => {
        if (!contentRef.current || !processedHtmlContent) {
            console.log('[PlayableContentViewer] Effect: Skipped (no contentRef or processedHtmlContent)');
            return;
        }
        console.log('[PlayableContentViewer] Effect: Running for processedHtmlContent:', processedHtmlContent);

        setError(null); // Clear previous errors on new content

        const handleAmpersoundClick = async (event) => {
            console.log('[PlayableContentViewer] handleAmpersoundClick: Fired for event target:', event.target);
            const target = event.target.closest('.ampersound-tag');
            if (!target) {
                console.log('[PlayableContentViewer] handleAmpersoundClick: No .ampersound-tag found on target or ancestors.');
                return;
            }
            console.log('[PlayableContentViewer] handleAmpersoundClick: Found .ampersound-tag:', target);

            const username = target.dataset.username;
            const soundname = target.dataset.soundname;

            if (!username || !soundname) {
                console.warn('[PlayableContentViewer] handleAmpersoundClick: Ampersound span missing data attributes', target);
                return;
            }
            console.log(`[PlayableContentViewer] handleAmpersoundClick: Playing &${soundname} for @${username}`);

            const key = `${username}-${soundname}`;
            // Play from cache if available
            if (audioCacheRef.current.has(key)) {
                const cachedAudio = audioCacheRef.current.get(key);
                console.log('[PlayableContentViewer] handleAmpersoundClick: Playing cached audio:', cachedAudio);
                if (activeAudio && activeAudio !== cachedAudio) {
                    console.log('[PlayableContentViewer] handleAmpersoundClick: Pausing existing audio.');
                    activeAudio.pause();
                }
                cachedAudio.currentTime = 0; // Reset playback to start
                cachedAudio.play().catch(playError => {
                    console.error("[PlayableContentViewer] handleAmpersoundClick: Error playing cached audio:", playError);
                    setError(`Could not play sound: ${playError.message}. Browser autoplay policies might require user interaction for each sound.`);
                    cachedAudio.pause();
                    setActiveAudio(null); // Clear active audio if play fails
                });
                setActiveAudio(cachedAudio); // Store the cached audio element
                return;
            }

            try {
                const response = await fetch(`/api/v1/ampersounds/${username}/${soundname}`);
                if (!response.ok) {
                    const errData = await response.json();
                    console.error('[PlayableContentViewer] handleAmpersoundClick: Fetch error:', errData.message);
                    throw new Error(errData.message || `Could not fetch &${soundname} for @${username}`);
                }
                const data = await response.json();
                console.log('[PlayableContentViewer] handleAmpersoundClick: Fetch successful, data:', data);
                
                if (data.url) {
                    const newAudio = new Audio(data.url);
                    console.log('[PlayableContentViewer] handleAmpersoundClick: Attempting to play audio:', data.url);
                    audioCacheRef.current.set(key, newAudio); // Cache the audio element
                    newAudio.play().catch(playError => {
                        console.error("[PlayableContentViewer] handleAmpersoundClick: Error playing audio:", playError);
                        setError(`Could not play sound: ${playError.message}. Browser autoplay policies might require user interaction for each sound.`);
                        // Ensure previous activeAudio is cleared if new one fails to play
                        if (activeAudio && activeAudio !== newAudio) {
                            activeAudio.pause();
                        }
                        setActiveAudio(null); // Clear active audio if play fails
                    });
                    setActiveAudio(newAudio); // Store the new audio element
                } else {
                    console.error('[PlayableContentViewer] handleAmpersoundClick: Audio URL not found in response.');
                    throw new Error('Audio URL not found in response.');
                }

            } catch (err) {
                console.error("[PlayableContentViewer] handleAmpersoundClick: Catch block error:", err);
                setError(err.message);
                if (activeAudio) { // Ensure cleanup if error occurs after an audio was active
                    activeAudio.pause();
                }
                setActiveAudio(null);
            }
        };

        const spans = contentRef.current.querySelectorAll('.ampersound-tag');
        console.log('[PlayableContentViewer] Effect: Found spans:', spans.length, spans);

        spans.forEach((span, index) => {
            console.log(`[PlayableContentViewer] Effect: Attaching listener to span ${index + 1}/${spans.length}`, span);
            span.addEventListener('click', handleAmpersoundClick);
        });

        // Cleanup: remove event listeners when component unmounts or htmlContent changes
        return () => {
            console.log('[PlayableContentViewer] Effect Cleanup: Removing listeners for processedHtmlContent:', processedHtmlContent);
            spans.forEach((span, index) => {
                console.log(`[PlayableContentViewer] Effect Cleanup: Removing listener from span ${index + 1}/${spans.length}`, span);
                span.removeEventListener('click', handleAmpersoundClick);
            });
            // The other useEffect handles activeAudio cleanup on unmount or when activeAudio itself changes.
            // No need to call setActiveAudio(null) here directly as it might interfere with the other effect.
        };
    }, [processedHtmlContent, activeAudio]); // MODIFIED: use processedHtmlContent

    return (
        <div>
            {error && <p style={{ color: 'red' }}>Error: {error}</p>}
            <div ref={contentRef} dangerouslySetInnerHTML={{ __html: processedHtmlContent }} />
        </div>
    );
};

export default PlayableContentViewer;
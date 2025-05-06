import React, { useEffect, useRef, useState } from 'react';

const PlayableContentViewer = ({ htmlContent }) => {
    const contentRef = useRef(null);
    const [activeAudio, setActiveAudio] = useState(null);
    const [error, setError] = useState(null);

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
        if (!contentRef.current || !htmlContent) return;

        setError(null); // Clear previous errors on new content

        const handleAmpersoundClick = async (event) => {
            const target = event.target.closest('.ampersound-tag');
            if (!target) return;

            const username = target.dataset.username;
            const soundname = target.dataset.soundname;

            if (!username || !soundname) {
                console.warn('Ampersound span missing data attributes', target);
                return;
            }

            // If there's an active audio, stop it before playing a new one
            if (activeAudio) {
                activeAudio.pause();
                // setActiveAudio(null) will be called in the cleanup of the *other* useEffect
                // or before setting a new one. This prevents premature cleanup if setting same audio again (though unlikely here)
            }

            try {
                const response = await fetch(`/ampersounds/${username}/${soundname}`);
                if (!response.ok) {
                    const errData = await response.json();
                    throw new Error(errData.message || `Could not fetch &${soundname} for @${username}`);
                }
                const data = await response.json();
                
                if (data.url) {
                    const newAudio = new Audio(data.url);
                    newAudio.play().catch(playError => {
                        console.error("Error playing audio:", playError);
                        setError(`Could not play sound: ${playError.message}. Browser autoplay policies might require user interaction for each sound.`);
                        // Ensure previous activeAudio is cleared if new one fails to play
                        if (activeAudio && activeAudio !== newAudio) {
                            activeAudio.pause();
                        }
                        setActiveAudio(null); // Clear active audio if play fails
                    });
                    setActiveAudio(newAudio); // Store the new audio element
                } else {
                    throw new Error('Audio URL not found in response.');
                }

            } catch (err) {
                console.error("Error fetching or playing Ampersound:", err);
                setError(err.message);
                if (activeAudio) { // Ensure cleanup if error occurs after an audio was active
                    activeAudio.pause();
                }
                setActiveAudio(null);
            }
        };

        const spans = contentRef.current.querySelectorAll('.ampersound-tag');
        spans.forEach(span => {
            // Styles are applied by the .ampersound-tag CSS class
            span.addEventListener('click', handleAmpersoundClick);
        });

        // Cleanup: remove event listeners when component unmounts or htmlContent changes
        return () => {
            spans.forEach(span => {
                span.removeEventListener('click', handleAmpersoundClick);
            });
            // The other useEffect handles activeAudio cleanup on unmount or when activeAudio itself changes.
            // No need to call setActiveAudio(null) here directly as it might interfere with the other effect.
        };
    }, [htmlContent, activeAudio]); // Rerun effect if htmlContent or activeAudio changes

    return (
        <div>
            {error && <p style={{ color: 'red' }}>Error: {error}</p>}
            <div ref={contentRef} dangerouslySetInnerHTML={{ __html: htmlContent }} />
        </div>
    );
};

export default PlayableContentViewer; 
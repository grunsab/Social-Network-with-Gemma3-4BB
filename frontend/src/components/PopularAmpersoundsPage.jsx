import React, { useState, useEffect, useRef } from 'react';
import { Link } from 'react-router-dom'; // For linking to user profiles
import { useAuth } from '../context/AuthContext'; // Import useAuth
import Spinner from './Spinner';
import { FaPlay, FaPause } from 'react-icons/fa'; // Import Play/Pause icons
import ReportButton from './ReportButton'; // Import ReportButton
import './PopularAmpersoundsPage.css'; // Import the CSS file
import { formatToLocalDateTime, formatToLocalDate } from '../utils/dateUtils';

const PopularAmpersoundsPage = () => {
    const { currentUser } = useAuth(); // Get currentUser
    const [ampersounds, setAmpersounds] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState('');
    const [playbackError, setPlaybackError] = useState(''); // Specific error for playback
    const [currentlyPlaying, setCurrentlyPlaying] = useState(null); // { id: soundId, audio: audioObject }
    const [loadingSound, setLoadingSound] = useState(null); // Track which sound is loading

    // Cleanup audio on unmount
    useEffect(() => {
        return () => {
            if (currentlyPlaying?.audio) {
                currentlyPlaying.audio.pause();
            }
        };
    }, [currentlyPlaying]);

    useEffect(() => {
        const fetchPopularAmpersounds = async () => {
            setLoading(true);
            setError('');
            setPlaybackError('');
            try {
                // Credentials needed if this endpoint ever becomes protected,
                // but for a public listing, it might not be.
                // For consistency with other fetches that might need it, let's include it.
                const response = await fetch('/api/v1/ampersounds/all', {
                    credentials: 'include' 
                });
                if (!response.ok) {
                    const data = await response.json();
                    throw new Error(data.message || 'Failed to fetch popular ampersounds');
                }
                const data = await response.json();
                setAmpersounds(data || []);
            } catch (err) {
                console.error("Error fetching popular ampersounds:", err);
                setError(err.message || 'Could not load popular ampersounds.');
            } finally {
                setLoading(false);
            }
        };

        fetchPopularAmpersounds();
    }, []);

    const handlePlayToggle = async (sound) => {
        setPlaybackError('');
        setLoadingSound(sound.id); // Indicate loading for this sound

        // If this sound is already playing, pause it
        if (currentlyPlaying?.id === sound.id) {
            currentlyPlaying.audio.pause();
            setCurrentlyPlaying(null);
            setLoadingSound(null);
            return;
        }

        // If another sound is playing, pause it first
        if (currentlyPlaying?.audio) {
            currentlyPlaying.audio.pause();
            setCurrentlyPlaying(null); // Clear previous
        }

        try {
            // Fetch the sound URL AND increment count via the backend endpoint
            const response = await fetch(`/ampersounds/${sound.user.username}/${sound.name}`, {
                 credentials: 'include'
            });
             if (!response.ok) {
                const errData = await response.json();
                throw new Error(errData.message || `Could not fetch &${sound.name}`);
            }
            const data = await response.json();

            if (data.url) {
                // Update the play count in the local state immediately
                setAmpersounds(prevSounds => prevSounds.map(s => 
                    s.id === sound.id ? { ...s, play_count: data.play_count ?? s.play_count } : s
                ));

                // Play the audio
                const audio = new Audio(data.url);
                setCurrentlyPlaying({ id: sound.id, audio: audio });
                
                audio.play().catch(playError => {
                    console.error("Error playing audio:", playError);
                    setPlaybackError(`Could not play &${sound.name}: ${playError.message}`);
                    setCurrentlyPlaying(null); // Clear playing state on error
                });

                // Add event listener to clear playing state when audio finishes
                audio.onended = () => {
                    setCurrentlyPlaying(null);
                };

            } else {
                 throw new Error('Audio URL not found in response.');
            }

        } catch (err) {
            console.error(`Error playing &${sound.name}:`, err);
            setPlaybackError(`Error playing &${sound.name}: ${err.message}`);
            setCurrentlyPlaying(null);
        } finally {
            setLoadingSound(null); // Stop loading indicator for this sound
        }
    };

    if (loading) return <Spinner contained={true} />;
    if (error) return <p className="error-message">Error: {error}</p>;

    return (
        <div className="popular-ampersounds-page card"> {/* Using card class for basic styling */}
            <h2>Popular Ampersounds (Most Played First)</h2>
            {playbackError && <p className="error-message">Playback Error: {playbackError}</p>}
            {ampersounds.length === 0 ? (
                <p>No ampersounds to display at the moment.</p>
            ) : (
                <ul className="ampersound-list"> {/* Re-use class from Profile.css or create new ones */}
                    {ampersounds.map(sound => (
                        <li key={sound.id} className="ampersound-list-item">
                            {/* Play/Pause Button */} 
                            <button 
                                onClick={() => handlePlayToggle(sound)}
                                className={`ampersound-play-button icon-button ${currentlyPlaying?.id === sound.id ? 'playing' : ''}`}
                                disabled={loadingSound === sound.id} // Disable while loading this sound
                                title={currentlyPlaying?.id === sound.id ? `Pause &${sound.name}` : `Play &${sound.name}`}
                            >
                                {loadingSound === sound.id ? (
                                    <Spinner inline={true} size="small" />
                                ) : currentlyPlaying?.id === sound.id ? (
                                    <FaPause /> 
                                ) : (
                                    <FaPlay />
                                )}
                            </button>
                            <div className="ampersound-info">
                                <span className="ampersound-name">&{sound.name}</span>
                                <span className="ampersound-author"> by 
                                    <Link to={`/profile/${sound.user.username}`}>@{sound.user.username}</Link>
                                </span>
                                <span className="ampersound-timestamp">
                                    ({formatToLocalDate(sound.timestamp)})
                                </span>
                                <span className="ampersound-play-count">
                                     - {sound.play_count ?? 0} plays
                                </span>
                            </div>
                            {/* Report Button for Ampersound */}
                            {currentUser && currentUser.id !== sound.user.id && (
                                <ReportButton 
                                    contentId={sound.id} 
                                    contentType="ampersound" 
                                    reportedUserId={sound.user.id}
                                />
                            )}
                        </li>
                    ))}
                </ul>
            )}
        </div>
    );
};

export default PopularAmpersoundsPage;
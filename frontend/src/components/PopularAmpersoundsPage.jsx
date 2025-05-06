import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom'; // For linking to user profiles
import Spinner from './Spinner';
// You might want a specific CSS file for this page later
// import './PopularAmpersoundsPage.css';

const PopularAmpersoundsPage = () => {
    const [ampersounds, setAmpersounds] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState('');

    useEffect(() => {
        const fetchPopularAmpersounds = async () => {
            setLoading(true);
            setError('');
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

    if (loading) return <Spinner contained={true} />;
    if (error) return <p className="error-message">Error: {error}</p>;

    return (
        <div className="popular-ampersounds-page card"> {/* Using card class for basic styling */}
            <h2>Popular Ampersounds (Most Played First)</h2>
            {ampersounds.length === 0 ? (
                <p>No ampersounds to display at the moment.</p>
            ) : (
                <ul className="ampersound-list"> {/* Re-use class from Profile.css or create new ones */}
                    {ampersounds.map(sound => (
                        <li key={sound.id} className="ampersound-list-item">
                            <div className="ampersound-info">
                                <span className="ampersound-name">&{sound.name}</span>
                                <span className="ampersound-author"> by 
                                    <Link to={`/profile/${sound.user.username}`}>@{sound.user.username}</Link>
                                </span>
                                <span className="ampersound-timestamp">
                                    ({new Date(sound.timestamp).toLocaleDateString()})
                                </span>
                                <span className="ampersound-play-count">
                                     - {sound.play_count ?? 0} plays
                                </span>
                            </div>
                            {sound.url && <audio controls src={sound.url} className="ampersound-audio-player"></audio>}
                        </li>
                    ))}
                </ul>
            )}
        </div>
    );
};

export default PopularAmpersoundsPage; 
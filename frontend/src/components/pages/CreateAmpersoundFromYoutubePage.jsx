import React, { useState, useContext } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext'; // Import useAuth hook
import './CreateAmpersoundFromYoutubePage.css'; // We'll create this CSS file later

function CreateAmpersoundFromYoutubePage() {
    const [youtubeUrl, setYoutubeUrl] = useState('');
    const [startTime, setStartTime] = useState('');
    const [endTime, setEndTime] = useState('');
    const [ampersoundName, setAmpersoundName] = useState('');
    const [privacy, setPrivacy] = useState('public');
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState(null);
    const [successMessage, setSuccessMessage] = useState(null);
    const navigate = useNavigate();
    const { currentUser } = useAuth(); // Get currentUser to ensure user is logged in, or for other purposes

    const handleSubmit = async (e) => {
        e.preventDefault();
        setIsLoading(true);
        setError(null);
        setSuccessMessage(null);

        if (!currentUser) { // Optional: Check if user is logged in via context
            setError('You must be logged in to create an ampersound.');
            setIsLoading(false);
            // navigate('/login'); // Optionally redirect to login
            return;
        }

        if (!youtubeUrl.trim()) {
            setError('YouTube URL is required.');
            setIsLoading(false);
            return;
        }
        if (!ampersoundName.trim()) {
            setError('Ampersound name is required.');
            setIsLoading(false);
            return;
        }
        if (startTime === '' || endTime === '') {
            setError('Start and End times are required.');
            setIsLoading(false);
            return;
        }

        const startSec = parseInt(startTime, 10);
        const endSec = parseInt(endTime, 10);

        if (isNaN(startSec) || isNaN(endSec) || startSec < 0 || endSec <= 0) {
            setError('Start and End times must be valid positive numbers.');
            setIsLoading(false);
            return;
        }

        if (startSec >= endSec) {
            setError('Start time must be less than end time.');
            setIsLoading(false);
            return;
        }
        
        // Optional: Add more sophisticated URL validation if needed
        // const youtubeRegex = /^(https?:\/\/)?(www\.)?(youtube\.com\/watch\?v=|youtu\.be\/)([\w-]+)(\&.*|\?.*)?$/;
        // if (!youtubeRegex.test(youtubeUrl)) {
        //     setError('Invalid YouTube URL format.');
        //     setIsLoading(false);
        //     return;
        // }

        try {
            const response = await fetch('/api/v1/ampersounds/from_youtube', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                credentials: 'include', // Add for cookie-based auth if needed (good practice)
                body: JSON.stringify({
                    youtube_url: youtubeUrl,
                    start_time: startSec,
                    end_time: endSec,
                    name: ampersoundName,
                    privacy: privacy,
                }),
            });

            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.message || `HTTP error! status: ${response.status}`);
            }

            setSuccessMessage(`Ampersound '${data.name}' created successfully! It is pending approval.`);
            // Optionally, clear the form or navigate away
            setYoutubeUrl('');
            setStartTime('');
            setEndTime('');
            setAmpersoundName('');
            setPrivacy('public');
            // navigate('/my-ampersounds'); // Example navigation

        } catch (err) {
            console.error("Failed to create ampersound:", err);
            setError(err.message || 'An unexpected error occurred. Please try again.');
        } finally {
            setIsLoading(false);
        }
    };

    return (
        <div className="create-ampersound-youtube-container">
            <h2>Create Ampersound from YouTube</h2>
            <form onSubmit={handleSubmit} className="create-ampersound-form">
                {error && <p className="error-message">{error}</p>}
                {successMessage && <p className="success-message">{successMessage}</p>}

                <div className="form-group">
                    <label htmlFor="youtubeUrl">YouTube Video URL:</label>
                    <input
                        type="url"
                        id="youtubeUrl"
                        value={youtubeUrl}
                        onChange={(e) => setYoutubeUrl(e.target.value)}
                        placeholder="e.g., https://www.youtube.com/watch?v=dQw4w9WgXcQ"
                        required
                    />
                </div>

                <div className="form-group">
                    <label htmlFor="ampersoundName">Ampersound Name (&name):</label>
                    <input
                        type="text"
                        id="ampersoundName"
                        value={ampersoundName}
                        onChange={(e) => setAmpersoundName(e.target.value)}
                        placeholder="e.g., coolSound (no spaces or '&')"
                        required
                    />
                </div>

                <div className="form-group time-inputs">
                    <div>
                        <label htmlFor="startTime">Start Time (seconds):</label>
                        <input
                            type="number"
                            id="startTime"
                            value={startTime}
                            onChange={(e) => setStartTime(e.target.value)}
                            placeholder="e.g., 10"
                            min="0"
                            required
                        />
                    </div>
                    <div>
                        <label htmlFor="endTime">End Time (seconds):</label>
                        <input
                            type="number"
                            id="endTime"
                            value={endTime}
                            onChange={(e) => setEndTime(e.target.value)}
                            placeholder="e.g., 25"
                            min="0"
                            required
                        />
                    </div>
                </div>

                <div className="form-group">
                    <label htmlFor="privacy">Privacy:</label>
                    <select id="privacy" value={privacy} onChange={(e) => setPrivacy(e.target.value)}>
                        <option value="public">Public</option>
                        <option value="friends">Friends Only</option>
                    </select>
                </div>

                <button type="submit" disabled={isLoading} className="submit-button">
                    {isLoading ? 'Creating...' : 'Create Ampersound'}
                </button>
            </form>
        </div>
    );
}

export default CreateAmpersoundFromYoutubePage; 
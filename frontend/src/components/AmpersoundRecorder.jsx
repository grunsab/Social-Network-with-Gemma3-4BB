import React, { useState, useRef } from 'react';
import './AmpersoundRecorder.css'; // Import the CSS file

const AmpersoundRecorder = () => {
    const [isRecording, setIsRecording] = useState(false);
    const [audioBlob, setAudioBlob] = useState(null);
    const [ampersoundName, setAmpersoundName] = useState('');
    const [error, setError] = useState(null);
    const [successMessage, setSuccessMessage] = useState(null);
    const [isLoading, setIsLoading] = useState(false);

    const mediaRecorderRef = useRef(null);
    const audioChunksRef = useRef([]);
    const streamRef = useRef(null); // To keep track of the stream for stopping tracks

    const handleStartRecording = async () => {
        setError(null);
        setSuccessMessage(null);
        setAudioBlob(null);
        if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
            setError('getUserMedia not supported on your browser!');
            return;
        }
        try {
            streamRef.current = await navigator.mediaDevices.getUserMedia({ audio: true });
            
            let options = { mimeType: 'audio/webm' };
            if (!MediaRecorder.isTypeSupported(options.mimeType)) {
                console.warn(`${options.mimeType} is not Supported. Trying audio/webm; codecs=opus`);
                options = { mimeType: 'audio/webm; codecs=opus' };
                if (!MediaRecorder.isTypeSupported(options.mimeType)) {
                    console.warn(`${options.mimeType} is not Supported. Trying audio/ogg; codecs=opus`);
                    options = { mimeType: 'audio/ogg; codecs=opus' };
                    if (!MediaRecorder.isTypeSupported(options.mimeType)) {
                        console.warn(`${options.mimeType} is not Supported. Using browser default.`);
                        options = {}; // Use browser default
                    }
                }
            }
            
            mediaRecorderRef.current = new MediaRecorder(streamRef.current, options);
            console.log("MediaRecorder initialized. Requested options:", options, "Actual mimeType:", mediaRecorderRef.current.mimeType);
            audioChunksRef.current = [];

            mediaRecorderRef.current.ondataavailable = (event) => {
                audioChunksRef.current.push(event.data);
            };

            mediaRecorderRef.current.onstop = () => {
                const actualMimeType = mediaRecorderRef.current?.mimeType || 'audio/webm'; 
                console.log("Creating blob with MIME type:", actualMimeType);
                const blob = new Blob(audioChunksRef.current, { type: actualMimeType });
                setAudioBlob(blob);
                // Stop microphone tracks using the stored stream reference
                if (streamRef.current) {
                    streamRef.current.getTracks().forEach(track => track.stop());
                    streamRef.current = null; // Clear the ref once tracks are stopped
                }
            };

            mediaRecorderRef.current.start();
            setIsRecording(true);
        } catch (err) {
            console.error("Error starting recording:", err);
            setError(`Error starting recording: ${err.message}. Please ensure microphone access is allowed.`);
            setIsRecording(false); // Ensure state is reset
            if (streamRef.current) { // Clean up stream if an error occurred after getting it
                streamRef.current.getTracks().forEach(track => track.stop());
                streamRef.current = null;
            }
        }
    };

    const handleStopRecording = () => {
        if (mediaRecorderRef.current && mediaRecorderRef.current.state === "recording") {
            mediaRecorderRef.current.stop(); // This will trigger the onstop handler
            setIsRecording(false);
        } else if (streamRef.current) {
             // If recording never started but stream was acquired, clean it up.
             streamRef.current.getTracks().forEach(track => track.stop());
             streamRef.current = null;
             setIsRecording(false); // Ensure UI consistency
        }
    };

    const handleSaveAmpersound = async () => {
        if (!audioBlob) {
            setError("No audio recorded to save.");
            return;
        }
        if (!ampersoundName.trim()) {
            setError("Please provide a name for your Ampersound.");
            return;
        }
        if (/[^a-zA-Z0-9_]/.test(ampersoundName)) {
            setError("Ampersound name can only contain letters, numbers, and underscores.");
            return;
        }

        setIsLoading(true);
        setError(null);
        setSuccessMessage(null);

        const formData = new FormData();
        // Determine file extension based on the recorder's actual mimeType
        const actualMimeType = mediaRecorderRef.current?.mimeType || 'audio/webm';
        let fileExtension = '.webm';
        if (actualMimeType.includes('ogg')) {
            fileExtension = '.ogg';
        } else if (actualMimeType.includes('mp4')) { // Example for another possible type
            fileExtension = '.mp4'; 
        } else if (actualMimeType.includes('aac')) { // Example
            fileExtension = '.aac';
        }
        // Add more conditions if other mimeTypes are expected from the fallback chain
        
        formData.append('audio_file', audioBlob, `${ampersoundName.trim()}${fileExtension}`);
        formData.append('name', ampersoundName.trim());

        try {
            const response = await fetch('/api/v1/ampersounds', {
                method: 'POST',
                body: formData,
                credentials: 'include' 
            });

            const data = await response.json();

            if (response.ok) {
                setSuccessMessage(`Ampersound "${ampersoundName}" saved successfully! Tag: &${ampersoundName}`);
                setAmpersoundName('');
                setAudioBlob(null);
            } else {
                setError(data.message || "Failed to save Ampersound.");
            }
        } catch (err) {
            console.error("Error saving Ampersound:", err);
            setError("An error occurred while saving the Ampersound. Please try again.");
        } finally {
            setIsLoading(false);
        }
    };

    return (
        <div className="ampersound-recorder">
            <h3>Create New Ampersound</h3>
            {error && <p className="error-message" style={{ color: 'red' }}>Error: {error}</p>}
            {successMessage && <p className="success-message" style={{ color: 'green' }}>{successMessage}</p>}
            
            <div>
                <label htmlFor="ampersoundName">Name (e.g., &hello): &</label>
                <input
                    type="text"
                    id="ampersoundName"
                    value={ampersoundName}
                    onChange={(e) => setAmpersoundName(e.target.value)}
                    placeholder="your_sound_name"
                    disabled={isRecording || isLoading || !!audioBlob}
                />
            </div>

            {!isRecording && !audioBlob && (
                <button onClick={handleStartRecording} disabled={isLoading}>Start Recording</button>
            )}
            {isRecording && (
                <button onClick={handleStopRecording} disabled={isLoading}>Stop Recording</button>
            )}

            {audioBlob && !isRecording && (
                <div>
                    <p>Recording finished. Preview:</p>
                    <audio src={URL.createObjectURL(audioBlob)} controls />
                    <button onClick={handleSaveAmpersound} disabled={isLoading || !ampersoundName.trim()}>
                        {isLoading ? 'Saving...' : 'Save Ampersound'}
                    </button>
                    <button onClick={() => { setAudioBlob(null); setAmpersoundName(''); setError(null); setSuccessMessage(null);}} disabled={isLoading} style={{backgroundColor: 'grey'}}>
                        Record New / Discard
                    </button>
                </div>
            )}
        </div>
    );
};

export default AmpersoundRecorder; 
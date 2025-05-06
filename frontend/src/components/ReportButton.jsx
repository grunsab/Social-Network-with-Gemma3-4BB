import React, { useState } from 'react';
import { useAuth } from '../context/AuthContext'; // To get currentUser for checks
import { FaFlag } from 'react-icons/fa'; // Icon for reporting
import './ReportButton.css'; // Optional: for styling

function ReportButton({ contentId, contentType, reportedUserId }) {
  const { currentUser } = useAuth();
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');
  const [successMessage, setSuccessMessage] = useState('');
  const [showConfirmation, setShowConfirmation] = useState(false);
  const [reason, setReason] = useState('');

  if (!currentUser) {
    return null; // Don't show button if user is not logged in
  }

  // Prevent users from reporting their own content
  if (currentUser && reportedUserId && currentUser.id === reportedUserId) {
    return null;
  }

  const handleReportClick = () => {
    setShowConfirmation(true);
    setError('');
    setSuccessMessage('');
  };

  const handleConfirmReport = async () => {
    if (!contentId || !contentType) {
      setError('Missing content information for report.');
      setShowConfirmation(false);
      return;
    }

    setIsLoading(true);
    setError('');
    setSuccessMessage('');

    try {
      const response = await fetch('/api/v1/reports', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          // Assuming your API requires authentication, include token if necessary
          // 'Authorization': `Bearer ${currentUser.token}` // Example
        },
        body: JSON.stringify({ 
          content_id: contentId, 
          content_type: contentType,
          reason: reason
        }),
      });

      const responseData = await response.json();

      if (!response.ok) {
        throw new Error(responseData.message || 'Failed to submit report.');
      }

      setSuccessMessage(responseData.message || 'Report submitted successfully.');
      setReason(''); // Clear reason
    } catch (err) {
      console.error('Error submitting report:', err);
      setError(err.message || 'Could not submit report.');
    } finally {
      setIsLoading(false);
      setShowConfirmation(false); // Close confirmation dialog
    }
  };

  const handleCancelReport = () => {
    setShowConfirmation(false);
    setReason('');
    setError('');
  };

  if (successMessage) {
    return <span className="report-button-success">Reported!</span>;
  }

  return (
    <>
      <button 
        onClick={handleReportClick} 
        disabled={isLoading}
        className="report-button icon-button" 
        title={`Report this ${contentType}`}
      >
        <FaFlag />
      </button>

      {showConfirmation && (
        <div className="report-confirmation-modal">
          <div className="report-confirmation-content">
            <h4>Confirm Report</h4>
            <p>Are you sure you want to report this {contentType}?</p>
            <textarea 
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              placeholder="Optional: Reason for reporting..."
              rows={3}
            />
            {error && <p className="error-message">{error}</p>}
            <div className="report-confirmation-actions">
              <button onClick={handleConfirmReport} disabled={isLoading} className="confirm">
                {isLoading ? 'Submitting...' : 'Confirm'}
              </button>
              <button onClick={handleCancelReport} disabled={isLoading} className="cancel">
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}

export default ReportButton; 
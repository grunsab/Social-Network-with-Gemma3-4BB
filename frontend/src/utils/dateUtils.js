
export const formatToLocalDateTime = (isoTimestamp) => {
  if (!isoTimestamp) return '';
  try {
    return new Date(isoTimestamp).toLocaleString();
  } catch (error) {
    console.error("Error formatting timestamp:", isoTimestamp, error);
    return 'Invalid date'; // Or return the original string, or a specific error message
  }
};

export const formatToLocalDate = (isoTimestamp) => {
  if (!isoTimestamp) return '';
  try {
    return new Date(isoTimestamp).toLocaleDateString();
  } catch (error) {
    console.error("Error formatting date:", isoTimestamp, error);
    return 'Invalid date';
  }
};

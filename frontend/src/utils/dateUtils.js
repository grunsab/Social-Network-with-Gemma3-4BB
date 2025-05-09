export const formatToLocalDateTime = (isoTimestamp) => {
  if (!isoTimestamp) return '';
  try {
    let parsableTimestamp = isoTimestamp;
    // If timestamp is in 'YYYY-MM-DD HH:MM:SS' format, replace space with 'T'
    if (parsableTimestamp.includes(' ') && !parsableTimestamp.includes('T')) {
        parsableTimestamp = parsableTimestamp.replace(' ', 'T');
    }
    // If timestamp string doesn't end with Z or an offset, assume it's UTC
    if (!parsableTimestamp.endsWith('Z') && !/[-+]\d{2}:\d{2}$/.test(parsableTimestamp)) {
      parsableTimestamp += 'Z';
    }
    return new Date(parsableTimestamp).toLocaleString();
  } catch (error) {
    console.error("Error formatting timestamp:", isoTimestamp, error);
    return 'Invalid date'; // Or return the original string, or a specific error message
  }
};

export const formatToLocalDate = (isoTimestamp) => {
  if (!isoTimestamp) return '';
  try {
    let parsableTimestamp = isoTimestamp;
    // If timestamp is in 'YYYY-MM-DD HH:MM:SS' format, replace space with 'T'
    if (parsableTimestamp.includes(' ') && !parsableTimestamp.includes('T')) {
        parsableTimestamp = parsableTimestamp.replace(' ', 'T');
    }
    // If timestamp string doesn't end with Z or an offset, assume it's UTC
    if (!parsableTimestamp.endsWith('Z') && !/[-+]\d{2}:\d{2}$/.test(parsableTimestamp)) {
      parsableTimestamp += 'Z';
    }
    return new Date(parsableTimestamp).toLocaleDateString();
  } catch (error) {
    console.error("Error formatting date:", isoTimestamp, error);
    return 'Invalid date';
  }
};

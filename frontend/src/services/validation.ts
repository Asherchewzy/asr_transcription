const MAX_FILE_SIZE_MB = Number(import.meta.env.VITE_MAX_FILE_SIZE) || 10; // 10MB default
const MAX_FILE_SIZE = MAX_FILE_SIZE_MB * 1024 * 1024;
const ALLOWED_TYPES = (import.meta.env.VITE_ALLOWED_FILE_TYPES || 'audio/mpeg,audio/mp3').split(',');

export interface ValidationResult {
  valid: boolean;
  error?: string;
}

export function validateFile(file: File): ValidationResult {
  // Check file type
  if (!ALLOWED_TYPES.includes(file.type)) {
    return {
      valid: false,
      error: `Invalid file type. Only ${ALLOWED_TYPES.join(', ')} files are allowed.`
    };
  }

  // Check file size
  if (file.size > MAX_FILE_SIZE) {
    const maxSizeMB = Math.round(MAX_FILE_SIZE / (1024 * 1024));
    return {
      valid: false,
      error: `File too large. Maximum size is ${maxSizeMB}MB.`
    };
  }

  return { valid: true };
}

export function validateFiles(files: File[]): ValidationResult {
  for (const file of files) {
    const result = validateFile(file);
    if (!result.valid) {
      return result;
    }
  }
  return { valid: true };
}

import React, { useState } from 'react';
import {
  Container,
  Paper,
  Typography,
  Box,
  Button,
  LinearProgress,
  Alert,
  Card,
  CardContent,
  TextField,
  MenuItem
} from '@mui/material';
import CloudUploadIcon from '@mui/icons-material/CloudUpload';
import { useNavigate } from 'react-router-dom';

const availableCourses = [
  { id: 'DAA', label: 'DAA' },
  { id: 'SoftSkill', label: 'Soft Skill' },
  { id: 'ComputerNetworks', label: 'Computer Networks' },
  { id: 'OperatingSystems', label: 'Operating Systems' },
  { id: 'CloudDevelopment', label: 'Cloud Development' },
  { id: 'DataEngineering', label: 'Data Engineering' },
  { id: 'Aptitude', label: 'Aptitude' },
  { id: 'WebTechnology', label: 'Web Technology' }
];

function StudentUpload() {
  const [file, setFile] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [message, setMessage] = useState('');
  const [studentId, setStudentId] = useState('');
  const [courseId, setCourseId] = useState('');
  const navigate = useNavigate();

  const handleFileChange = (event) => {
    const selectedFile = event.target.files[0];
    if (selectedFile) {
      // Validate file type
      const allowedTypes = ['application/pdf', 'text/plain'];
      if (!allowedTypes.includes(selectedFile.type)) {
        setMessage('Please select a PDF or TXT file.');
        return;
      }

      // Validate file size (10MB limit)
      if (selectedFile.size > 10 * 1024 * 1024) {
        setMessage('File size must be less than 10MB.');
        return;
      }

      setFile(selectedFile);
      setMessage('');
    }
  };

  const handleUpload = async () => {
    if (!file) {
      setMessage('Please select a file first.');
      return;
    }

    setUploading(true);
    setMessage('');

    try {
      if (!studentId.trim()) {
        setMessage('Please enter your student ID.');
        setUploading(false);
        return;
      }

      if (!courseId) {
        setMessage('Please select a course for this submission.');
        setUploading(false);
        return;
      }

      const formData = new FormData();
      formData.append('file', file);
      formData.append('studentId', studentId.trim());
      formData.append('courseId', courseId);

      const response = await fetch('http://localhost:5000/upload', {
        method: 'POST',
        body: formData,
      });

      const result = await response.json();

      if (response.ok) {
        setMessage('Assignment uploaded successfully! Processing for plagiarism detection...');
        // Redirect to dashboard after a delay
        setTimeout(() => {
          navigate('/dashboard');
        }, 2000);
      } else {
        setMessage(result.error || 'Upload failed. Please try again.');
      }
    } catch (error) {
      setMessage('Network error. Please check your connection and try again.');
    } finally {
      setUploading(false);
    }
  };

  return (
    <Container maxWidth="md" sx={{ py: 4 }}>
      <Typography variant="h3" component="h1" gutterBottom align="center">
        Assignment Submission
      </Typography>
      <Typography variant="h6" color="text.secondary" align="center" sx={{ mb: 4 }}>
        Upload your assignment for plagiarism detection
      </Typography>

      <Card>
        <CardContent sx={{ p: 4 }}>
          <Box
            sx={{
              border: '2px dashed #ccc',
              borderRadius: 2,
              p: 4,
              textAlign: 'center',
              mb: 3,
              backgroundColor: file ? '#f0f8ff' : '#fafafa'
            }}
          >
            <input
              accept=".pdf,.txt"
              style={{ display: 'none' }}
              id="file-upload"
              type="file"
              onChange={handleFileChange}
            />
            <label htmlFor="file-upload">
              <Button
                variant="outlined"
                component="span"
                startIcon={<CloudUploadIcon />}
                sx={{ mb: 2 }}
              >
                Choose File
              </Button>
            </label>

            {file ? (
              <Typography variant="body1" sx={{ mt: 2 }}>
                Selected: <strong>{file.name}</strong> ({(file.size / 1024 / 1024).toFixed(2)} MB)
              </Typography>
            ) : (
              <Typography variant="body2" color="text.secondary">
                Supported formats: PDF, DOC, DOCX, TXT (Max 10MB)
              </Typography>
            )}
          </Box>

          <Box sx={{ mb: 3, display: 'grid', gap: 2 }}>
            <TextField
              label="Student ID"
              value={studentId}
              onChange={(e) => setStudentId(e.target.value)}
              fullWidth
              size="small"
            />
            <TextField
              label="Select Course"
              value={courseId}
              onChange={(e) => setCourseId(e.target.value)}
              select
              fullWidth
              size="small"
            >
              <MenuItem value="">Select a course</MenuItem>
              {availableCourses.map((course) => (
                <MenuItem key={course.id} value={course.id}>
                  {course.label}
                </MenuItem>
              ))}
            </TextField>
            <Box sx={{ textAlign: 'center' }}>
              <Button
                variant="contained"
                size="large"
                onClick={handleUpload}
                disabled={!file || uploading}
                sx={{ minWidth: 200 }}
              >
                {uploading ? 'Uploading...' : 'Upload Assignment'}
              </Button>
            </Box>
          </Box>

          {uploading && (
            <Box sx={{ mb: 3 }}>
              <LinearProgress />
              <Typography variant="body2" color="text.secondary" align="center" sx={{ mt: 1 }}>
                Processing your assignment...
              </Typography>
            </Box>
          )}

          {message && (
            <Alert severity={message.includes('successfully') ? 'success' : 'error'} sx={{ mt: 2 }}>
              {message}
            </Alert>
          )}
        </CardContent>
      </Card>
    </Container>
  );
}

export default StudentUpload;
import React, { useState, useEffect } from 'react';
import {
  Container,
  Typography,
  Paper,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TablePagination,
  Chip,
  Box,
  TextField,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Card,
  CardContent,
  Grid,
  LinearProgress,
  Alert,
  Button,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions
} from '@mui/material';
import { styled } from '@mui/material/styles';

const StyledTableRow = styled(TableRow)(({ theme }) => ({
  '&:nth-of-type(odd)': {
    backgroundColor: theme.palette.action.hover,
  },
  '&:hover': {
    backgroundColor: theme.palette.action.selected,
  },
}));

function TeacherDashboard() {
  const [submissions, setSubmissions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [page, setPage] = useState(0);
  const [rowsPerPage, setRowsPerPage] = useState(10);
  const [filters, setFilters] = useState({
    course: 'all',
    status: 'all',
    similarityThreshold: 0
  });
  const [selectedSubmission, setSelectedSubmission] = useState(null);
  const [detailDialogOpen, setDetailDialogOpen] = useState(false);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState('');

  useEffect(() => {
    fetchSubmissions();
  }, []);

  const fetchSubmissions = async () => {
    try {
      setLoading(true);
      const response = await fetch('http://localhost:5000/submissions');
      const data = await response.json();

      if (response.ok) {
        setSubmissions(data.submissions || []);
      } else {
        setError(data.error || 'Failed to fetch submissions');
      }
    } catch (err) {
      setError('Network error. Please check your connection.');
    } finally {
      setLoading(false);
    }
  };

  const handleFilterChange = (field, value) => {
    setFilters(prev => ({
      ...prev,
      [field]: value
    }));
    setPage(0); // Reset to first page when filtering
  };

  const getSimilarityColor = (score) => {
    if (score >= 0.8) return 'error';
    if (score >= 0.6) return 'warning';
    return 'success';
  };

  const getStatusColor = (status) => {
    switch (status) {
      case 'FLAGGED': return 'error';
      case 'REVIEWED': return 'success';
      case 'PROCESSING': return 'warning';
      default: return 'default';
    }
  };

  // Filter submissions based on current filters
  const filteredSubmissions = submissions.filter(submission => {
    if (filters.course !== 'all' && submission.courseId !== filters.course) return false;
    if (filters.status !== 'all' && submission.status !== filters.status) return false;
    if (submission.similarityScore < filters.similarityThreshold) return false;
    return true;
  });

  // Paginate results
  const paginatedSubmissions = filteredSubmissions.slice(
    page * rowsPerPage,
    page * rowsPerPage + rowsPerPage
  );

  const handleChangePage = (event, newPage) => {
    setPage(newPage);
  };

  const handleChangeRowsPerPage = (event) => {
    setRowsPerPage(parseInt(event.target.value, 10));
    setPage(0);
  };

  const handleDeleteSubmission = async (submissionId) => {
    if (!window.confirm('Delete this submission and its uploaded file?')) {
      return;
    }

    try {
      const response = await fetch(`http://localhost:5000/submissions/${submissionId}`, {
        method: 'DELETE'
      });

      const result = await response.json();
      if (response.ok) {
        setSubmissions((prev) => prev.filter((submission) => submission.id !== submissionId));
      } else {
        setError(result.error || 'Failed to delete submission');
      }
    } catch (err) {
      setError('Network error. Unable to delete submission.');
    }
  };

  const openSubmissionDetails = async (submissionId) => {
    try {
      setDetailLoading(true);
      setDetailError('');
      const response = await fetch(`http://localhost:5000/submissions/${submissionId}`);
      const data = await response.json();
      if (response.ok) {
        setSelectedSubmission(data.submission);
        setSubmissions((prev) => prev.map((submission) =>
          submission.id === data.submission.id
            ? {
                ...submission,
                status: data.submission.status,
                flagged: data.submission.flagged,
                similarityScore: data.submission.similarityScore
              }
            : submission
        ));
        setDetailDialogOpen(true);
      } else {
        setDetailError(data.error || 'Failed to load submission details');
      }
    } catch (err) {
      setDetailError('Network error. Unable to load submission details.');
    } finally {
      setDetailLoading(false);
    }
  };

  const closeSubmissionDetails = () => {
    setSelectedSubmission(null);
    setDetailDialogOpen(false);
    setDetailError('');
  };

  const handleMarkReviewed = async (submissionId) => {
    try {
      const response = await fetch(`http://localhost:5000/submissions/${submissionId}/review`, {
        method: 'PATCH'
      });
      const data = await response.json();
      if (response.ok) {
        fetchSubmissions();
        closeSubmissionDetails();
      } else {
        setDetailError(data.error || 'Failed to mark reviewed');
      }
    } catch (err) {
      setDetailError('Network error. Unable to mark reviewed.');
    }
  };

  const handleFlagSubmission = async (submissionId) => {
    try {
      const response = await fetch(`http://localhost:5000/submissions/${submissionId}/flag`, {
        method: 'PATCH'
      });
      const data = await response.json();
      if (response.ok) {
        fetchSubmissions();
      } else {
        setError(data.error || 'Failed to flag submission');
      }
    } catch (err) {
      setError('Network error. Unable to flag submission.');
    }
  };

  if (loading) {
    return (
      <Container maxWidth="lg" sx={{ py: 4 }}>
        <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '60vh' }}>
          <Box sx={{ width: '100%', maxWidth: 400 }}>
            <LinearProgress />
            <Typography variant="body1" align="center" sx={{ mt: 2 }}>
              Loading submissions...
            </Typography>
          </Box>
        </Box>
      </Container>
    );
  }

  return (
    <Container maxWidth="lg" sx={{ py: 4 }}>
      <Typography variant="h3" component="h1" gutterBottom>
        Teacher Dashboard
      </Typography>
      <Typography variant="h6" color="text.secondary" sx={{ mb: 4 }}>
        Review student submissions and plagiarism reports
      </Typography>

      {error && (
        <Alert severity="error" sx={{ mb: 3 }}>
          {error}
        </Alert>
      )}

      {/* Stats Cards */}
      <Grid container spacing={3} sx={{ mb: 4 }}>
        <Grid item xs={12} sm={6} md={3}>
          <Card>
            <CardContent>
              <Typography color="text.secondary" gutterBottom>
                Total Submissions
              </Typography>
              <Typography variant="h4">
                {submissions.length}
              </Typography>
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <Card>
            <CardContent>
              <Typography color="text.secondary" gutterBottom>
                Flagged for Review
              </Typography>
              <Typography variant="h4" color="error">
                {submissions.filter(s => s.status === 'FLAGGED').length}
              </Typography>
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <Card>
            <CardContent>
              <Typography color="text.secondary" gutterBottom>
                Average Similarity
              </Typography>
              <Typography variant="h4">
                {submissions.length > 0
                  ? (submissions.reduce((sum, s) => sum + (s.similarityScore || 0), 0) / submissions.length * 100).toFixed(1)
                  : 0}%
              </Typography>
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <Card>
            <CardContent>
              <Typography color="text.secondary" gutterBottom>
                Reviewed
              </Typography>
              <Typography variant="h4" color="success.main">
                {submissions.filter(s => s.status === 'REVIEWED').length}
              </Typography>
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      {/* Filters */}
      <Paper sx={{ p: 3, mb: 3 }}>
        <Typography variant="h6" gutterBottom>
          Filters
        </Typography>
        <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap' }}>
          <FormControl size="small" sx={{ minWidth: 120 }}>
            <InputLabel>Course</InputLabel>
            <Select
              value={filters.course}
              label="Course"
              onChange={(e) => handleFilterChange('course', e.target.value)}
            >
              <MenuItem value="all">All Courses</MenuItem>
              <MenuItem value="course123">Computer Science 101</MenuItem>
              <MenuItem value="course456">Data Structures</MenuItem>
            </Select>
          </FormControl>

          <FormControl size="small" sx={{ minWidth: 120 }}>
            <InputLabel>Status</InputLabel>
            <Select
              value={filters.status}
              label="Status"
              onChange={(e) => handleFilterChange('status', e.target.value)}
            >
              <MenuItem value="all">All Status</MenuItem>
              <MenuItem value="FLAGGED">Flagged</MenuItem>
              <MenuItem value="REVIEWED">Reviewed</MenuItem>
              <MenuItem value="PROCESSING">Processing</MenuItem>
            </Select>
          </FormControl>

          <TextField
            size="small"
            label="Min Similarity %"
            type="number"
            value={filters.similarityThreshold * 100}
            onChange={(e) => handleFilterChange('similarityThreshold', parseInt(e.target.value) / 100)}
            InputProps={{ inputProps: { min: 0, max: 100 } }}
            sx={{ width: 150 }}
          />
        </Box>
      </Paper>

      {/* Submissions Table */}
      <Paper>
        <TableContainer>
          <Table>
            <TableHead>
              <TableRow>
                <TableCell>Student ID</TableCell>
                <TableCell>Course</TableCell>
                <TableCell>File Name</TableCell>
                <TableCell>Submitted</TableCell>
                <TableCell>Similarity Score</TableCell>
                <TableCell>Status</TableCell>
                <TableCell>Actions</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {paginatedSubmissions.map((submission) => (
                <StyledTableRow key={submission.id}>
                  <TableCell>{submission.studentId}</TableCell>
                  <TableCell>{submission.courseId}</TableCell>
                  <TableCell>{submission.fileName}</TableCell>
                  <TableCell>{new Date(submission.createdAt).toLocaleDateString()}</TableCell>
                  <TableCell>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                      <LinearProgress
                        variant="determinate"
                        value={(submission.similarityScore || 0) * 100}
                        color={getSimilarityColor(submission.similarityScore || 0)}
                        sx={{ width: 60, height: 8 }}
                      />
                      <Typography variant="body2">
                        {((submission.similarityScore || 0) * 100).toFixed(1)}%
                      </Typography>
                    </Box>
                  </TableCell>
                  <TableCell>
                    <Chip
                      label={submission.status}
                      color={getStatusColor(submission.status)}
                      size="small"
                    />
                  </TableCell>
                  <TableCell sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
                    <Button size="small" variant="outlined" onClick={() => openSubmissionDetails(submission.id)}>
                      View Details
                    </Button>
                    {submission.status !== 'FLAGGED' && submission.status !== 'REVIEWED' && (
                      <Button
                        size="small"
                        variant="outlined"
                        color="warning"
                        onClick={() => handleFlagSubmission(submission.id)}
                      >
                        Flag
                      </Button>
                    )}
                    <Button
                      size="small"
                      variant="outlined"
                      color="error"
                      onClick={() => handleDeleteSubmission(submission.id)}
                    >
                      Delete
                    </Button>
                  </TableCell>
                </StyledTableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
        <TablePagination
          component="div"
          count={filteredSubmissions.length}
          page={page}
          onPageChange={handleChangePage}
          rowsPerPage={rowsPerPage}
          onRowsPerPageChange={handleChangeRowsPerPage}
        />
      </Paper>

      <Dialog open={detailDialogOpen} onClose={closeSubmissionDetails} fullWidth maxWidth="md">
        <DialogTitle>Submission Details</DialogTitle>
        <DialogContent dividers>
          {detailLoading ? (
            <Typography>Loading details…</Typography>
          ) : detailError ? (
            <Alert severity="error">{detailError}</Alert>
          ) : selectedSubmission ? (
            <Box sx={{ display: 'grid', gap: 2 }}>
              <Typography><strong>Student ID:</strong> {selectedSubmission.studentId}</Typography>
              <Typography><strong>Course ID:</strong> {selectedSubmission.courseId}</Typography>
              <Typography><strong>File:</strong> {selectedSubmission.fileName}</Typography>
              <Typography><strong>Status:</strong> {selectedSubmission.status}</Typography>
              <Typography><strong>Similarity Score:</strong> {((selectedSubmission.similarityScore || 0) * 100).toFixed(1)}%</Typography>
              <Typography><strong>Flagged:</strong> {selectedSubmission.flagged ? 'Yes' : 'No'}</Typography>
              <Typography><strong>Matched Submission:</strong> {selectedSubmission.matchedSubmissionId || 'None'}</Typography>
              <Typography variant="subtitle1" sx={{ mt: 2 }}><strong>Extracted Text</strong></Typography>
              <Paper variant="outlined" sx={{ p: 2, maxHeight: 320, overflow: 'auto', whiteSpace: 'pre-wrap' }}>
                {selectedSubmission.extractedText || 'No extracted text available.'}
              </Paper>
            </Box>
          ) : null}
        </DialogContent>
        <DialogActions>
          {selectedSubmission && selectedSubmission.status !== 'REVIEWED' && (
            <Button onClick={() => handleMarkReviewed(selectedSubmission.id)} color="success">
              Mark Reviewed
            </Button>
          )}
          <Button onClick={closeSubmissionDetails}>Close</Button>
        </DialogActions>
      </Dialog>
    </Container>
  );
}

export default TeacherDashboard;
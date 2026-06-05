import React, { useState, useEffect } from 'react';
import Joyride, { STATUS } from 'react-joyride';

const ProductTour = () => {
  const [run, setRun] = useState(false);

  useEffect(() => {
    // Check if the user has completed the tour
    const hasCompletedTour = localStorage.getItem('altsan_tour_completed');
    if (!hasCompletedTour) {
      // Delay slightly to let the UI mount and animations settle
      setTimeout(() => setRun(true), 1500);
    }
  }, []);

  const steps = [
    {
      target: '.header-user-info',
      content: 'Welcome to Altsan! Here you can see your current role and identity.',
      disableBeacon: true,
    },
    {
      target: '.hero-card',
      content: 'This is your main dashboard. Keep an eye out here for high-priority updates.',
    },
    {
      target: '.floating-bottom-nav',
      content: 'Use this bottom command bar to navigate the app with one hand.',
    },
    {
      target: '.notif-btn',
      content: 'Click the Bell icon to view your slide-over Notification Center and enable OS-level Push Alerts!',
    },
    {
      target: '.theme-toggle',
      content: 'Toggle Dark Mode on or off using this button. Give it a try!',
    }
  ];

  const handleJoyrideCallback = (data) => {
    const { status } = data;
    const finishedStatuses = [STATUS.FINISHED, STATUS.SKIPPED];

    if (finishedStatuses.includes(status)) {
      setRun(false);
      localStorage.setItem('altsan_tour_completed', 'true');
    }
  };

  return (
    <Joyride
      steps={steps}
      run={run}
      continuous={true}
      scrollToFirstStep={true}
      showProgress={true}
      showSkipButton={true}
      callback={handleJoyrideCallback}
      styles={{
        options: {
          zIndex: 10000,
          primaryColor: '#3b82f6',
          backgroundColor: '#ffffff',
          textColor: '#0f172a',
          overlayColor: 'rgba(15, 23, 42, 0.6)',
        },
        tooltip: {
          borderRadius: '16px',
          fontFamily: "'Inter', sans-serif",
          boxShadow: '0 20px 40px rgba(0,0,0,0.15)',
        },
        buttonNext: {
          borderRadius: '8px',
          fontWeight: 600,
        },
        buttonBack: {
          color: '#64748b',
        },
        buttonSkip: {
          color: '#94a3b8',
        }
      }}
    />
  );
};

export default ProductTour;

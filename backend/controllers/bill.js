const axios = require('axios');
const FormData = require('form-data');
const BillAnalysis = require('../models/BillAnalysis');
const FootprintLog = require('../models/FootprintLog');
const { awardPoints } = require('../services/gamification');
const { calculateEnergy } = require('../services/carbonCalc');

const calculateCarbonFootprint = (value, unit) => {
  const uLower = (unit || '').toLowerCase();
  if (uLower === 'kwh') {
    return parseFloat(calculateEnergy(value).toFixed(2));
  } else if (uLower === 'therms') {
    return parseFloat((value * 5.3).toFixed(2));
  } else if (uLower === 'gallons' || uLower === 'gallon') {
    return parseFloat((value * 0.003).toFixed(2));
  } else if (uLower === 'liters' || uLower === 'liter') {
    return parseFloat((value * 0.0008).toFixed(2));
  } else if (uLower === 'ccf') {
    return parseFloat((value * 5.5).toFixed(2));
  } else {
    return parseFloat((value * 0.4).toFixed(2));
  }
};

const calculateTrend = async (userId, currentPeriod, currentValue, currentCost, currentUnit) => {
  try {
    const history = await BillAnalysis.find({
      user_id: userId,
      consumption_unit: currentUnit
    });

    const filteredHistory = history.filter(h => h.billing_period !== currentPeriod);

    if (filteredHistory.length === 0) {
      return {
        percentage_change: 0.0,
        direction: 'stable',
        compared_to_period: 'none',
        previous_value: 0.0,
        previous_cost: 0.0
      };
    }

    filteredHistory.sort((a, b) => b.billing_period.localeCompare(a.billing_period));
    const prevBill = filteredHistory[0];

    const prevVal = prevBill.consumption_value || 0.0;
    const prevCost = prevBill.total_cost || 0.0;

    let pctChange = 0.0;
    if (prevVal > 0) {
      pctChange = ((currentValue - prevVal) / prevVal) * 100;
    }

    const direction = pctChange >= 0 ? 'increase' : 'decrease';

    return {
      percentage_change: parseFloat(Math.abs(pctChange).toFixed(2)),
      direction,
      compared_to_period: prevBill.billing_period,
      previous_value: prevVal,
      previous_cost: prevCost
    };
  } catch (err) {
    console.error('Error calculating bill trends:', err.message);
    return {
      percentage_change: 0.0,
      direction: 'stable',
      compared_to_period: 'error',
      previous_value: 0.0,
      previous_cost: 0.0
    };
  }
};

const uploadBill = async (req, res) => {
  try {
    if (!req.file) {
      return res.status(400).json({ detail: 'No statement file uploaded.' });
    }

    const userId = req.user._id;
    const aiServiceUrl = process.env.AI_SERVICE_URL || 'http://127.0.0.1:8001';

    // 1. Forward file to Python AI Service
    const form = new FormData();
    form.append('file', req.file.buffer, {
      filename: req.file.originalname,
      contentType: req.file.mimetype
    });

    let aiResponse;
    try {
      aiResponse = await axios.post(`${aiServiceUrl}/ai/ocr/bill`, form, {
        headers: {
          ...form.getHeaders()
        }
      });
    } catch (err) {
      console.error('Failed to parse bill on AI microservice:', err.message);
      return res.status(502).json({ detail: 'AI microservice is unavailable or returned an error.' });
    }

    const {
      billing_period,
      consumption_value,
      consumption_unit,
      total_cost,
      savings_opportunities,
      extracted_raw_text
    } = aiResponse.data;

    // 2. Compute carbon footprint
    const carbonFootprint = calculateCarbonFootprint(consumption_value, consumption_unit);

    // 3. Compute trend comparison
    const trendData = await calculateTrend(
      userId,
      billing_period,
      consumption_value,
      total_cost,
      consumption_unit
    );

    // 4. Save bill analysis
    const billEntry = new BillAnalysis({
      user_id: userId,
      file_url: req.file.originalname,
      billing_period,
      consumption_value,
      consumption_unit,
      total_cost,
      carbon_footprint_kg: carbonFootprint,
      savings_opportunities,
      trend: trendData,
      extracted_raw_text: (extracted_raw_text || '').slice(0, 1000),
      analyzed_at: new Date()
    });

    const savedBill = await billEntry.save();

    // 5. Save footprint log
    let category = 'energy';
    const uLower = consumption_unit.toLowerCase();
    if (uLower === 'therms') {
      category = 'gas';
    } else if (['gallons', 'liters', 'ccf', 'gallon', 'liter'].includes(uLower)) {
      category = 'water'; // Note: Frontend might map water or gas category
    }

    const footprintEntry = new FootprintLog({
      user_id: userId,
      date: new Date(),
      categories: {
        [category]: {
          usage: consumption_value,
          unit: consumption_unit,
          co2_kg: carbonFootprint
        }
      },
      total_co2_kg: carbonFootprint
    });
    await footprintEntry.save();

    // 6. Award gamification points
    try {
      await awardPoints(userId, 'bill_upload');
    } catch (err) {
      console.error('Failed to award bill upload points:', err.message);
    }

    const resObj = savedBill.toObject();
    resObj._id = resObj._id.toString();
    resObj.user_id = resObj.user_id.toString();

    res.json(resObj);
  } catch (error) {
    console.error('Upload bill error:', error);
    res.status(500).json({ detail: 'Internal Server Error' });
  }
};

const getBills = async (req, res) => {
  try {
    const userId = req.user._id;
    const history = await BillAnalysis.find({ user_id: userId }).sort({ analyzed_at: -1 });
    
    const formatted = history.map(h => {
      const hObj = h.toObject();
      hObj._id = hObj._id.toString();
      hObj.user_id = hObj.user_id.toString();
      return hObj;
    });

    res.json(formatted);
  } catch (error) {
    console.error('Get bills history error:', error);
    res.status(500).json({ detail: 'Internal Server Error' });
  }
};

module.exports = {
  uploadBill,
  getBills
};

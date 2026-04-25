import 'dart:convert';
import 'dart:typed_data';

import 'package:file_saver/file_saver.dart';
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;

const Color primaryBlue = Color(0xFF3D6AE8);
const Color pageBg = Color(0xFFF6F8FC);
const Color cardBg = Colors.white;
const Color borderColor = Color(0xFFE2E8F0);
const Color textMain = Color(0xFF0F172A);
const Color textMuted = Color(0xFF64748B);
const Color errorRed = Color(0xFFDC2626);

final RegExp mrnRegex = RegExp(r'^[A-Za-z]{3}\d{3}$');

const Map<String, List<Map<String, dynamic>>> scaleOptions = {
  'intensity': [
    {'label': 'Not at all', 'value': 0},
    {'label': 'A little', 'value': 1},
    {'label': 'Moderately', 'value': 2},
    {'label': 'Quite a bit', 'value': 3},
    {'label': 'Extremely', 'value': 4},
  ],
  'frequency': [
    {'label': 'Never', 'value': 0},
    {'label': 'Rarely', 'value': 1},
    {'label': 'Sometimes', 'value': 2},
    {'label': 'Often', 'value': 3},
    {'label': 'Very often', 'value': 4},
  ],
  'agreement': [
    {'label': 'Strongly disagree', 'value': 0},
    {'label': 'Disagree', 'value': 1},
    {'label': 'Neutral', 'value': 2},
    {'label': 'Agree', 'value': 3},
    {'label': 'Strongly agree', 'value': 4},
  ],
  'confidence': [
    {'label': 'Not at all confident', 'value': 0},
    {'label': 'Slightly confident', 'value': 1},
    {'label': 'Moderately confident', 'value': 2},
    {'label': 'Very confident', 'value': 3},
    {'label': 'Extremely confident', 'value': 4},
  ],
  'clarity': [
    {'label': 'Not at all clear', 'value': 0},
    {'label': 'Slightly clear', 'value': 1},
    {'label': 'Moderately clear', 'value': 2},
    {'label': 'Mostly clear', 'value': 3},
    {'label': 'Completely clear', 'value': 4},
  ],
  'support': [
    {'label': 'No support', 'value': 0},
    {'label': 'A little support', 'value': 1},
    {'label': 'Moderate support', 'value': 2},
    {'label': 'Strong support', 'value': 3},
    {'label': 'Very strong support', 'value': 4},
  ],
};

String normalizeMrnInput(String s) => s.replaceAll(RegExp(r'\s+'), '').toUpperCase();

String get apiBase {
  const fromEnv = String.fromEnvironment('VITE_API_BASE');
  if (fromEnv.isNotEmpty) {
    return fromEnv.endsWith('/') ? fromEnv.substring(0, fromEnv.length - 1) : fromEnv;
  }
  const flutterEnv = String.fromEnvironment('API_BASE');
  if (flutterEnv.isNotEmpty) {
    return flutterEnv.endsWith('/') ? flutterEnv.substring(0, flutterEnv.length - 1) : flutterEnv;
  }
  return 'http://127.0.0.1:8000/api';
}

List<Map<String, dynamic>> optionsForScale(String? scale) {
  return scaleOptions[scale] ?? scaleOptions['intensity']!;
}

String answerLabelForScale(String? scale, int? value) {
  if (value == null || value < 0 || value > 4) return '';
  return optionsForScale(scale)[value]['label'].toString();
}

InputDecoration appInputDecoration({
  required String hintText,
  bool hasError = false,
}) {
  return InputDecoration(
    hintText: hintText,
    hintStyle: const TextStyle(color: textMuted),
    filled: true,
    fillColor: Colors.white,
    contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 16),
    border: OutlineInputBorder(
      borderRadius: BorderRadius.circular(12),
      borderSide: BorderSide(color: hasError ? errorRed : borderColor),
    ),
    enabledBorder: OutlineInputBorder(
      borderRadius: BorderRadius.circular(12),
      borderSide: BorderSide(color: hasError ? errorRed : borderColor),
    ),
    focusedBorder: OutlineInputBorder(
      borderRadius: BorderRadius.circular(12),
      borderSide: BorderSide(color: hasError ? errorRed : primaryBlue, width: 1.4),
    ),
  );
}

class ApiService {
  static Future<Map<String, dynamic>> getQuestionnaire({String surgery = ''}) async {
    final uri = Uri.parse('$apiBase/questionnaire').replace(
      queryParameters: surgery.trim().isEmpty ? null : {'surgery': surgery},
    );
    final res = await http.get(uri);
    if (res.statusCode < 200 || res.statusCode >= 300) {
      throw Exception('GET /questionnaire failed: ${res.statusCode} ${res.body}');
    }
    return jsonDecode(res.body) as Map<String, dynamic>;
  }

  static Future<Map<String, dynamic>> submitAnswers({
    required String mrn,
    required String surgery,
    required String questionnaireId,
    required List<Map<String, dynamic>> responses,
  }) async {
    final res = await http.post(
      Uri.parse('$apiBase/submit'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({
        'mrn': mrn,
        'surgery': surgery,
        'questionnaire_id': questionnaireId,
        'responses': responses,
      }),
    );
    if (res.statusCode < 200 || res.statusCode >= 300) {
      throw Exception('POST /submit failed: ${res.statusCode} ${res.body}');
    }
    return jsonDecode(res.body) as Map<String, dynamic>;
  }

  static Future<Map<String, dynamic>> aiChat(Map<String, dynamic> payload) async {
    final res = await http.post(
      Uri.parse('$apiBase/ai/chat'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode(payload),
    );
    if (res.statusCode < 200 || res.statusCode >= 300) {
      throw Exception('POST /ai/chat failed: ${res.statusCode} ${res.body}');
    }
    return jsonDecode(res.body) as Map<String, dynamic>;
  }

  static Future<void> downloadDoctorReportPDF(Map<String, dynamic> reportPayload) async {
    final res = await http.post(
      Uri.parse('$apiBase/ai/report/pdf'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode(reportPayload),
    );
    if (res.statusCode < 200 || res.statusCode >= 300) {
      throw Exception('POST /ai/report/pdf failed: ${res.statusCode} ${res.body}');
    }

    final Uint8List bytes = res.bodyBytes;
    final String mrn = (reportPayload['mrn'] ?? 'patient').toString();
    await FileSaver.instance.saveFile(
      name: 'doctor_report_$mrn',
      bytes: bytes,
      ext: 'pdf',
      mimeType: MimeType.pdf,
    );
  }
}

void main() {
  runApp(const PsychScreeningApp());
}

class PsychScreeningApp extends StatelessWidget {
  const PsychScreeningApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      debugShowCheckedModeBanner: false,
      title: 'Pre-Operative Psychological Screening',
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(seedColor: primaryBlue),
        scaffoldBackgroundColor: pageBg,
        useMaterial3: true,
        fontFamily: 'Inter',
      ),
      home: const QuestionnairePage(),
    );
  }
}

enum AppStep { intro, form, results, chat }

class QuestionnairePage extends StatefulWidget {
  const QuestionnairePage({super.key});

  @override
  State<QuestionnairePage> createState() => _QuestionnairePageState();
}

class _QuestionnairePageState extends State<QuestionnairePage> {
  AppStep step = AppStep.intro;
  String mrn = '';
  String mrnError = '';
  String surgery = '';
  List<Map<String, dynamic>> questions = [];
  Map<int, int> responses = {};
  String? questionnaireId;
  Map<String, dynamic>? result;
  String error = '';

  final TextEditingController mrnController = TextEditingController();
  final TextEditingController surgeryController = TextEditingController();
  final TextEditingController messageController = TextEditingController();

  List<Map<String, String>> history = [];
  String chatError = '';
  bool ended = false;
  bool loading = false;

  @override
  void dispose() {
    mrnController.dispose();
    surgeryController.dispose();
    messageController.dispose();
    super.dispose();
  }

  String validateMrn(String value) {
    final clean = normalizeMrnInput(value);
    if (clean.isEmpty) return 'MRN required';
    if (!mrnRegex.hasMatch(clean)) return 'Invalid MRN format (RTY786)';
    return '';
  }

  void resetAll() {
    setState(() {
      step = AppStep.intro;
      mrn = '';
      mrnError = '';
      surgery = '';
      questions = [];
      responses = {};
      questionnaireId = null;
      result = null;
      error = '';
      history = [];
      chatError = '';
      ended = false;
      loading = false;
    });
    mrnController.text = '';
    surgeryController.text = '';
    messageController.text = '';
  }

  bool get allAnswered {
    if (questions.isEmpty) return false;
    return questions.every((q) => responses[q['id'] as int] != null);
  }

  Future<void> handleStart() async {
    setState(() {
      error = '';
    });

    final clean = normalizeMrnInput(mrnController.text);
    final err = validateMrn(clean);

    setState(() {
      mrn = clean;
      mrnError = err;
      surgery = surgeryController.text;
    });

    mrnController.text = clean;
    if (err.isNotEmpty) return;

    try {
      setState(() => loading = true);
      final data = await ApiService.getQuestionnaire(surgery: surgeryController.text);
      final rawQuestions = ((data['questions'] as List?) ?? []).cast<dynamic>();

      setState(() {
        questions = rawQuestions.map((e) => Map<String, dynamic>.from(e as Map)).toList();
        questionnaireId = (data['questionnaire_id'] ?? '').toString();
        responses = {};
        result = null;
        step = AppStep.form;
      });
    } catch (_) {
      setState(() {
        error = 'Failed to load questionnaire. Check backend console.';
      });
    } finally {
      if (mounted) setState(() => loading = false);
    }
  }

  Future<void> handleSubmit() async {
    setState(() {
      error = '';
    });

    final clean = normalizeMrnInput(mrnController.text.isEmpty ? mrn : mrnController.text);
    final err = validateMrn(clean);

    setState(() {
      mrn = clean;
      mrnError = err;
    });

    if (err.isNotEmpty) {
      setState(() => step = AppStep.intro);
      return;
    }

    if (!allAnswered) {
      setState(() {
        error = 'Please answer all questions before submitting.';
      });
      return;
    }

    try {
      setState(() => loading = true);
      final res = await ApiService.submitAnswers(
        mrn: clean,
        surgery: surgery,
        questionnaireId: questionnaireId ?? '',
        responses: questions
            .map(
              (q) => {
                'question_id': q['id'],
                'answer': responses[q['id'] as int],
              },
            )
            .toList(),
      );

      setState(() {
        result = res;
        step = AppStep.results;
      });
    } catch (_) {
      setState(() {
        error = 'Submit failed. Check backend console.';
      });
    } finally {
      if (mounted) setState(() => loading = false);
    }
  }

  Future<void> sendMessage() async {
    setState(() => chatError = '');
    final m = messageController.text.trim();
    if (m.isEmpty || ended) return;

    final nextHistory = [...history, {'role': 'user', 'content': m}];
    setState(() {
      history = nextHistory;
      messageController.clear();
      loading = true;
    });

    try {
      final res = await ApiService.aiChat({
        'mrn': mrn,
        'surgery': surgery,
        'message': m,
        'context': {
          'items': questions
              .map(
                (q) => {
                  'id': q['id'],
                  'theory': q['theory'],
                  'question': q['text'],
                  'answer': responses[q['id'] as int],
                  'scale': q['scale'] ?? 'intensity',
                },
              )
              .toList(),
        },
        'history': nextHistory,
      });

      setState(() {
        history = [
          ...history,
          {
            'role': 'assistant',
            'content': (res['answer'] ?? '').toString(),
          }
        ];
      });
    } catch (_) {
      setState(() {
        chatError = 'AI request failed. Check backend console.';
      });
    } finally {
      if (mounted) setState(() => loading = false);
    }
  }

  Future<void> downloadPdf() async {
    try {
      setState(() => chatError = '');
      await ApiService.downloadDoctorReportPDF({
        'mrn': mrn,
        'surgery': surgery,
        'ai_scores': result?['ai_scores'] ?? {},
        'ai_risk_color': result?['ai_risk_color'] ?? 'yellow',
        'ai_risk_percent': result?['ai_risk_percent'] ?? 50.0,
        'ai_explanation': result?['ai_explanation'] ?? '',
        'ai_key_signals': result?['ai_key_signals'] ?? [],
        'conversation': history,
        'questions': questions,
        'responses': responses.map((k, v) => MapEntry(k.toString(), v)),
      });
    } catch (_) {
      setState(() {
        chatError = 'PDF download failed. Check backend console.';
      });
    }
  }

  String get riskLabel {
    final color = (result?['ai_risk_color'] ?? '').toString().toLowerCase();
    if (color == 'green') return 'Low (Green)';
    if (color == 'yellow') return 'Moderate (Yellow)';
    if (color == 'orange') return 'High (Orange)';
    return 'Critical (Red)';
  }

  @override
  Widget build(BuildContext context) {
    switch (step) {
      case AppStep.intro:
        return _buildScaffold(_buildIntroCard());
      case AppStep.form:
        return _buildScaffold(_buildFormCard());
      case AppStep.results:
        return _buildScaffold(_buildResultsCard());
      case AppStep.chat:
        return _buildScaffold(_buildChatCard());
    }
  }

  Widget _buildScaffold(Widget child) {
    return Scaffold(
      body: Column(
        children: [
          Container(
            height: 72,
            decoration: const BoxDecoration(
              color: Colors.white,
              border: Border(bottom: BorderSide(color: borderColor)),
            ),
            padding: const EdgeInsets.symmetric(horizontal: 28),
            alignment: Alignment.centerLeft,
            child: Row(
              children: const [
                Icon(Icons.local_hospital_outlined, color: primaryBlue, size: 24),
                SizedBox(width: 10),
                Text(
                  'E-Hospital AI Screening',
                  style: TextStyle(
                    fontSize: 18,
                    fontWeight: FontWeight.w700,
                    color: textMain,
                  ),
                ),
              ],
            ),
          ),
          Expanded(
            child: Center(
              child: SingleChildScrollView(
                padding: const EdgeInsets.all(28),
                child: ConstrainedBox(
                  constraints: const BoxConstraints(maxWidth: 980),
                  child: child,
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildCardShell({
    required Widget child,
  }) {
    return Container(
      decoration: BoxDecoration(
        color: cardBg,
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: borderColor),
        boxShadow: const [
          BoxShadow(
            color: Color(0x140F172A),
            blurRadius: 24,
            offset: Offset(0, 8),
          )
        ],
      ),
      padding: const EdgeInsets.all(32),
      child: child,
    );
  }

  Widget _buildIntroCard() {
    return _buildCardShell(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          const Text(
            'Pre-Operative Psychological Screening',
            textAlign: TextAlign.center,
            style: TextStyle(
              fontSize: 46,
              height: 1.15,
              fontWeight: FontWeight.w700,
              color: textMain,
            ),
          ),
          const SizedBox(height: 18),
          const Text(
            'This screening helps summarize common psychological concerns before surgery. It is not a diagnosis and does not provide treatment decisions.',
            textAlign: TextAlign.center,
            style: TextStyle(fontSize: 18, color: textMuted, height: 1.7),
          ),
          const SizedBox(height: 24),
          Container(
            padding: const EdgeInsets.all(18),
            decoration: BoxDecoration(
              color: const Color(0xFFF8FAFC),
              borderRadius: BorderRadius.circular(14),
              border: Border.all(color: borderColor),
            ),
            child: const Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('• Answer based on how strongly each statement applies to you (0–4).', style: TextStyle(fontSize: 16, height: 1.8, color: textMain)),
                Text('• Questions are generated using established psychological theories (CBT, Stress & Coping, Info-Need, Safety).', style: TextStyle(fontSize: 16, height: 1.8, color: textMain)),
                Text('• You will receive an AI-generated explanation and can chat to discuss your concerns.', style: TextStyle(fontSize: 16, height: 1.8, color: textMain)),
              ],
            ),
          ),
          const SizedBox(height: 26),
          const Text(
            'Patient ID (MRN)',
            style: TextStyle(fontSize: 16, fontWeight: FontWeight.w700, color: textMain),
          ),
          const SizedBox(height: 8),
          TextField(
            controller: mrnController,
            maxLength: 6,
            onChanged: (v) {
              final clean = normalizeMrnInput(v);
              if (mrnController.text != clean) {
                mrnController.value = TextEditingValue(
                  text: clean,
                  selection: TextSelection.collapsed(offset: clean.length),
                );
              }
            },
            decoration: appInputDecoration(
              hintText: '3 letters + 3 numbers (e.g. RTY786)',
              hasError: mrnError.isNotEmpty,
            ).copyWith(counterText: ''),
          ),
          if (mrnError.isNotEmpty) ...[
            const SizedBox(height: 8),
            Text(
              mrnError,
              style: const TextStyle(color: errorRed, fontWeight: FontWeight.w700),
            ),
          ],
          const SizedBox(height: 18),
          const Text(
            'Surgery / Procedure (optional)',
            style: TextStyle(fontSize: 16, fontWeight: FontWeight.w700, color: textMain),
          ),
          const SizedBox(height: 8),
          TextField(
            controller: surgeryController,
            decoration: appInputDecoration(
              hintText: 'e.g., knee replacement, cataract surgery',
            ),
          ),
          const SizedBox(height: 24),
          SizedBox(
            height: 52,
            child: ElevatedButton(
              onPressed: loading ? null : handleStart,
              style: ElevatedButton.styleFrom(
                elevation: 0,
                backgroundColor: primaryBlue,
                foregroundColor: Colors.white,
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
              ),
              child: loading
                  ? const SizedBox(
                      width: 22,
                      height: 22,
                      child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white),
                    )
                  : const Text(
                      'Start Questionnaire',
                      style: TextStyle(fontSize: 17, fontWeight: FontWeight.w700),
                    ),
            ),
          ),
          if (error.isNotEmpty) ...[
            const SizedBox(height: 14),
            Text(
              error,
              textAlign: TextAlign.center,
              style: const TextStyle(color: errorRed, fontWeight: FontWeight.w700),
            ),
          ],
        ],
      ),
    );
  }

  Widget _buildFormCard() {
    return _buildCardShell(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          const Text(
            'Questionnaire',
            textAlign: TextAlign.center,
            style: TextStyle(
              fontSize: 40,
              fontWeight: FontWeight.w700,
              color: textMain,
            ),
          ),
          const SizedBox(height: 8),
          Text(
            surgery.trim().isEmpty ? 'Patient ID: $mrn' : 'Patient ID: $mrn  •  Procedure: $surgery',
            textAlign: TextAlign.center,
            style: const TextStyle(fontSize: 15, color: textMuted),
          ),
          const SizedBox(height: 18),
          const Text(
            'Choose the response that best matches each question.',
            style: TextStyle(fontSize: 16, color: textMuted, height: 1.7),
          ),
          if (error.isNotEmpty) ...[
            const SizedBox(height: 12),
            Text(
              error,
              textAlign: TextAlign.center,
              style: const TextStyle(color: errorRed, fontWeight: FontWeight.w700),
            ),
          ],
          const SizedBox(height: 18),
          ...questions.asMap().entries.map((entry) {
            final idx = entry.key;
            final q = entry.value;
            final qid = q['id'] as int;
            final scale = (q['scale'] ?? 'intensity').toString();
            final opts = optionsForScale(scale);
            final currentValue = responses[qid];

            return Container(
              margin: const EdgeInsets.only(bottom: 16),
              padding: const EdgeInsets.all(18),
              decoration: BoxDecoration(
                color: const Color(0xFFFBFDFF),
                borderRadius: BorderRadius.circular(14),
                border: Border.all(color: borderColor),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    '${idx + 1}. ${q['text']}',
                    style: const TextStyle(
                      fontSize: 20,
                      color: textMain,
                      fontWeight: FontWeight.w700,
                      height: 1.45,
                    ),
                  ),
                  const SizedBox(height: 12),
                  DropdownButtonFormField<int>(
                    value: currentValue,
                    decoration: appInputDecoration(hintText: 'Select response'),
                    hint: const Text('Select response'),
                    items: opts
                        .map(
                          (op) => DropdownMenuItem<int>(
                            value: op['value'] as int,
                            child: Text(op['label'].toString()),
                          ),
                        )
                        .toList(),
                    onChanged: (value) {
                      setState(() {
                        if (value != null) {
                          responses[qid] = value;
                        }
                      });
                    },
                  ),
                ],
              ),
            );
          }),
          const SizedBox(height: 8),
          SizedBox(
            height: 52,
            child: ElevatedButton(
              onPressed: loading ? null : handleSubmit,
              style: ElevatedButton.styleFrom(
                elevation: 0,
                backgroundColor: primaryBlue,
                foregroundColor: Colors.white,
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
              ),
              child: loading
                  ? const SizedBox(
                      width: 22,
                      height: 22,
                      child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white),
                    )
                  : const Text(
                      'Submit',
                      style: TextStyle(fontSize: 17, fontWeight: FontWeight.w700),
                    ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildResultsCard() {
    return _buildCardShell(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          const Text(
            'Result Summary',
            textAlign: TextAlign.center,
            style: TextStyle(fontSize: 40, fontWeight: FontWeight.w700, color: textMain),
          ),
          const SizedBox(height: 24),
          _buildSummaryRow(
            'AI Risk',
            '$riskLabel (${((result?['ai_risk_percent'] ?? 0) as num).toStringAsFixed(1)}%)',
          ),
          const SizedBox(height: 12),
          Container(
            padding: const EdgeInsets.all(18),
            decoration: BoxDecoration(
              color: const Color(0xFFF8FAFC),
              borderRadius: BorderRadius.circular(14),
              border: Border.all(color: borderColor),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text(
                  'AI Scores',
                  style: TextStyle(fontSize: 16, fontWeight: FontWeight.w700, color: textMain),
                ),
                const SizedBox(height: 10),
                Text('Anxiety: ${result?['ai_scores']?['anxiety'] ?? 0}', style: const TextStyle(fontSize: 15, color: textMain)),
                Text('Mood: ${result?['ai_scores']?['mood'] ?? 0}', style: const TextStyle(fontSize: 15, color: textMain)),
                Text('Info: ${result?['ai_scores']?['info'] ?? 0}', style: const TextStyle(fontSize: 15, color: textMain)),
                Text('Coping: ${result?['ai_scores']?['coping'] ?? 0}', style: const TextStyle(fontSize: 15, color: textMain)),
                Text('Safety: ${result?['ai_scores']?['safety'] ?? 0}', style: const TextStyle(fontSize: 15, color: textMain)),
              ],
            ),
          ),
          const SizedBox(height: 18),
          Container(
            padding: const EdgeInsets.all(18),
            decoration: BoxDecoration(
              color: const Color(0xFFF8FAFC),
              borderRadius: BorderRadius.circular(14),
              border: Border.all(color: borderColor),
            ),
            child: const Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'How to interpret these AI results',
                  style: TextStyle(fontSize: 16, fontWeight: FontWeight.w700, color: textMain),
                ),
                SizedBox(height: 8),
                Text(
                  'Each domain score is on a 0–16 scale (higher = stronger signal in that domain). As a quick guide: 0–4 low, 5–8 mild, 9–12 moderate, 13–16 high. Risk color summarizes overall concern level (Green=low → Red=critical).',
                  style: TextStyle(fontSize: 15, color: textMuted, height: 1.7),
                ),
                SizedBox(height: 8),
                Text('• Anxiety / Mood → Cognitive Behavioral Theory (CBT)', style: TextStyle(fontSize: 15, color: textMuted, height: 1.6)),
                Text('• Info → Information-Need & Uncertainty Reduction', style: TextStyle(fontSize: 15, color: textMuted, height: 1.6)),
                Text('• Coping → Stress & Coping Theory', style: TextStyle(fontSize: 15, color: textMuted, height: 1.6)),
                Text('• Safety → Psychological Safety & perceived support / trust', style: TextStyle(fontSize: 15, color: textMuted, height: 1.6)),
              ],
            ),
          ),
          const SizedBox(height: 24),
          Wrap(
            spacing: 12,
            runSpacing: 12,
            children: [
              ElevatedButton(
                onPressed: () => setState(() => step = AppStep.chat),
                style: ElevatedButton.styleFrom(
                  elevation: 0,
                  backgroundColor: primaryBlue,
                  foregroundColor: Colors.white,
                  padding: const EdgeInsets.symmetric(horizontal: 22, vertical: 16),
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                ),
                child: const Text('Continue to AI Conversation', style: TextStyle(fontSize: 16, fontWeight: FontWeight.w700)),
              ),
              OutlinedButton(
                onPressed: resetAll,
                style: OutlinedButton.styleFrom(
                  padding: const EdgeInsets.symmetric(horizontal: 22, vertical: 16),
                  side: const BorderSide(color: borderColor),
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                ),
                child: const Text('New Patient', style: TextStyle(fontSize: 16, color: textMain)),
              ),
            ],
          ),
          const SizedBox(height: 12),
          Text(
            'MRN: $mrn',
            textAlign: TextAlign.center,
            style: const TextStyle(fontSize: 14, color: textMuted),
          ),
        ],
      ),
    );
  }

  Widget _buildSummaryRow(String label, String value) {
    return Container(
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
        color: const Color(0xFFF8FAFC),
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: borderColor),
      ),
      child: Row(
        children: [
          Text(
            '$label:',
            style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w700, color: textMain),
          ),
          const SizedBox(width: 10),
          Expanded(
            child: Text(
              value,
              style: const TextStyle(fontSize: 16, color: textMain),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildChatCard() {
    final showIntroSummary = history.isEmpty;

    return _buildCardShell(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          const Text(
            'AI Conversation',
            textAlign: TextAlign.center,
            style: TextStyle(fontSize: 40, fontWeight: FontWeight.w700, color: textMain),
          ),
          const SizedBox(height: 8),
          const Text(
            'Non-diagnostic explanation only. No treatment decisions.',
            textAlign: TextAlign.center,
            style: TextStyle(fontSize: 17, color: textMuted),
          ),
          const SizedBox(height: 20),
          Container(
            padding: const EdgeInsets.all(18),
            decoration: BoxDecoration(
              color: const Color(0xFFF8FAFC),
              borderRadius: BorderRadius.circular(14),
              border: Border.all(color: borderColor),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Text('MRN: $mrn', style: const TextStyle(fontSize: 17, fontWeight: FontWeight.w700, color: textMain)),
                const SizedBox(height: 4),
                Text(
                  'AI Risk: $riskLabel (${((result?['ai_risk_percent'] ?? 0) as num).toStringAsFixed(1)}%)',
                  style: const TextStyle(fontSize: 17, fontWeight: FontWeight.w700, color: textMain),
                ),
                if (showIntroSummary) ...[
                  const SizedBox(height: 18),
                  const Text('AI Summary', style: TextStyle(fontSize: 18, fontWeight: FontWeight.w800, color: textMain)),
                  const SizedBox(height: 8),
                  Text(
                    (result?['ai_explanation'] ?? '').toString(),
                    style: const TextStyle(fontSize: 16, height: 1.7, color: textMain),
                    textAlign: TextAlign.justify,
                  ),
                  if (((result?['ai_key_signals'] as List?) ?? []).isNotEmpty) ...[
                    const SizedBox(height: 12),
                    const Text('Key signals', style: TextStyle(fontWeight: FontWeight.w800, color: textMain)),
                    const SizedBox(height: 6),
                    ...((result?['ai_key_signals'] as List?) ?? []).take(5).map(
                          (s) => Padding(
                            padding: const EdgeInsets.only(bottom: 6),
                            child: Text('• ${s.toString()}', textAlign: TextAlign.justify, style: const TextStyle(color: textMain)),
                          ),
                        ),
                  ],
                ],
              ],
            ),
          ),
          const SizedBox(height: 18),
          ...history.map((h) {
            final isUser = h['role'] == 'user';
            return Align(
              alignment: isUser ? Alignment.centerRight : Alignment.centerLeft,
              child: Container(
                constraints: const BoxConstraints(maxWidth: 760),
                margin: const EdgeInsets.only(top: 10),
                padding: const EdgeInsets.all(16),
                decoration: BoxDecoration(
                  color: isUser ? Colors.white : const Color(0xFFF1F5FF),
                  border: Border.all(color: isUser ? borderColor : const Color(0xFFD8E4FF)),
                  borderRadius: BorderRadius.circular(14),
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      isUser ? 'You' : 'AI',
                      style: TextStyle(
                        fontWeight: FontWeight.w800,
                        color: isUser ? textMain : primaryBlue,
                      ),
                    ),
                    const SizedBox(height: 6),
                    Text(
                      (h['content'] ?? '').toString(),
                      textAlign: TextAlign.justify,
                      style: const TextStyle(color: textMain, height: 1.6),
                    ),
                  ],
                ),
              ),
            );
          }),
          if (chatError.isNotEmpty) ...[
            const SizedBox(height: 12),
            Text(
              chatError,
              style: const TextStyle(color: errorRed, fontWeight: FontWeight.w700),
            ),
          ],
          const SizedBox(height: 18),
          Wrap(
            spacing: 10,
            runSpacing: 10,
            crossAxisAlignment: WrapCrossAlignment.center,
            children: [
              SizedBox(
                width: 620,
                child: TextField(
                  controller: messageController,
                  enabled: !ended,
                  decoration: appInputDecoration(
                    hintText: ended ? 'Conversation ended.' : 'Answer or ask a question...',
                  ),
                ),
              ),
              SizedBox(
                height: 52,
                child: ElevatedButton(
                  onPressed: ended || loading ? null : sendMessage,
                  style: ElevatedButton.styleFrom(
                    elevation: 0,
                    backgroundColor: primaryBlue,
                    foregroundColor: Colors.white,
                    padding: const EdgeInsets.symmetric(horizontal: 20),
                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                  ),
                  child: loading
                      ? const SizedBox(
                          width: 18,
                          height: 18,
                          child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white),
                        )
                      : const Text('Send', style: TextStyle(fontSize: 16, fontWeight: FontWeight.w700)),
                ),
              ),
            ],
          ),
          const SizedBox(height: 14),
          Wrap(
            spacing: 10,
            runSpacing: 10,
            children: [
              OutlinedButton(
                onPressed: () => setState(() => step = AppStep.results),
                style: OutlinedButton.styleFrom(
                  side: const BorderSide(color: borderColor),
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                  padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 14),
                ),
                child: const Text('Back to Results', style: TextStyle(fontSize: 16, color: textMain)),
              ),
              OutlinedButton(
                onPressed: resetAll,
                style: OutlinedButton.styleFrom(
                  side: const BorderSide(color: borderColor),
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                  padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 14),
                ),
                child: const Text('New Patient', style: TextStyle(fontSize: 16, color: textMain)),
              ),
              OutlinedButton(
                onPressed: () => setState(() => ended = true),
                style: OutlinedButton.styleFrom(
                  side: const BorderSide(color: borderColor),
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                  padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 14),
                ),
                child: const Text('End Conversation', style: TextStyle(fontSize: 16, color: textMain)),
              ),
              if (ended)
                ElevatedButton(
                  onPressed: downloadPdf,
                  style: ElevatedButton.styleFrom(
                    elevation: 0,
                    backgroundColor: primaryBlue,
                    foregroundColor: Colors.white,
                    padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 14),
                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                  ),
                  child: const Text('Download Doctor Report (PDF)', style: TextStyle(fontSize: 16, fontWeight: FontWeight.w700)),
                ),
            ],
          ),
        ],
      ),
    );
  }
}
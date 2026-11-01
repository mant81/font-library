package com.example.yumifont;

import android.app.Activity;
import android.os.Bundle;
import android.graphics.Typeface;
import android.graphics.Color;
import android.text.Editable;
import android.text.TextWatcher;
import android.util.TypedValue;
import android.view.View;
import android.view.ViewGroup;
import android.view.WindowInsetsController;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.SeekBar;
import android.widget.Switch;
import android.widget.TextView;
import java.text.Normalizer;

/** Offline handwriting preview, Android 8.0+. No device font settings are changed. */
public class MainActivity extends Activity {
    private static final String SAMPLE = "안녕하세요, 민보체 손글씨입니다.\n오늘의 작은 기록이 내일의 추억으로.\nHello minbo font! 0123456789 .,!?";
    private static final int INK = Color.rgb(41, 46, 42);
    private static final int GREEN = Color.rgb(57, 93, 69);
    private Typeface regular;
    private Typeface small;
    private TextView preview;
    private TextView sizeLabel;
    private EditText input;
    private Switch optical;
    private int size = 24;

    private int dp(int value) {
        return Math.round(value * getResources().getDisplayMetrics().density);
    }

    private TextView text(String value, int sp) {
        TextView view = new TextView(this);
        view.setText(value);
        view.setTextSize(sp);
        view.setTextColor(INK);
        view.setPadding(0, dp(8), 0, dp(8));
        return view;
    }

    private void updatePreview() {
        preview.setTypeface(optical.isChecked() ? small : regular);
        preview.setTextSize(TypedValue.COMPLEX_UNIT_SP, size);
        preview.setText(Normalizer.normalize(input.getText().toString(), Normalizer.Form.NFC));
        sizeLabel.setText("글자 크기 · " + size + "sp");
    }

    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        regular = getResources().getFont(R.font.minbo_regular);
        small = getResources().getFont(R.font.minbo_small);
        getWindow().getDecorView().setSystemUiVisibility(
            View.SYSTEM_UI_FLAG_LIGHT_STATUS_BAR | View.SYSTEM_UI_FLAG_LIGHT_NAVIGATION_BAR);
        if (android.os.Build.VERSION.SDK_INT >= 30) {
            getWindow().getInsetsController().setSystemBarsAppearance(
                WindowInsetsController.APPEARANCE_LIGHT_STATUS_BARS | WindowInsetsController.APPEARANCE_LIGHT_NAVIGATION_BARS,
                WindowInsetsController.APPEARANCE_LIGHT_STATUS_BARS | WindowInsetsController.APPEARANCE_LIGHT_NAVIGATION_BARS);
        }

        LinearLayout column = new LinearLayout(this);
        column.setOrientation(LinearLayout.VERTICAL);
        column.setFocusableInTouchMode(true);
        column.setPadding(dp(24), dp(16), dp(24), dp(32));
        TextView title = text("민보체", 36);
        title.setTypeface(regular);
        column.addView(title);
        TextView subtitle = text("minbo font  ·  0.1.3 시험판", 13);
        subtitle.setTextColor(GREEN);
        column.addView(subtitle);
        column.addView(text("내 문장 미리보기", 17));
        input = new EditText(this);
        input.setId(1001);
        input.setTextSize(16);
        input.setMinLines(3);
        input.setMaxLines(6);
        input.setGravity(android.view.Gravity.TOP);
        input.setHint("여기에 한글과 영문을 입력하세요");
        input.setContentDescription("미리볼 문장 입력");
        input.setInputType(android.text.InputType.TYPE_CLASS_TEXT | android.text.InputType.TYPE_TEXT_FLAG_MULTI_LINE);
        input.setText(state == null ? SAMPLE : state.getString("input", SAMPLE));
        column.addView(input, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));

        if (state != null) size = Math.max(7, Math.min(72, state.getInt("size", 24)));
        sizeLabel = text("", 14);
        column.addView(sizeLabel);
        SeekBar seek = new SeekBar(this);
        seek.setId(1002);
        seek.setContentDescription("글자 크기 7에서 72sp");
        seek.setMax(65);
        seek.setProgress(size - 7);
        column.addView(seek);
        optical = new Switch(this);
        optical.setId(1003);
        optical.setText("작은 글자용 보정본");
        optical.setPadding(0, dp(8), 0, dp(16));
        optical.setChecked(state == null ? size <= 15 : state.getBoolean("optical", size <= 15));
        column.addView(optical);

        preview = text("", 24);
        preview.setId(1004);
        preview.setTextIsSelectable(true);
        preview.setMinHeight(dp(130));
        preview.setBackgroundColor(Color.WHITE);
        preview.setPadding(dp(16), dp(16), dp(16), dp(16));
        preview.setLineSpacing(dp(5), 1.2f);
        preview.setContentDescription("민보체로 표시한 문장");
        column.addView(preview);
        LinearLayout actions = new LinearLayout(this);
        Button tiny = new Button(this);
        tiny.setText("7sp 확인");
        tiny.setAllCaps(false);
        tiny.setOnClickListener(v -> seek.setProgress(0));
        actions.addView(tiny, new LinearLayout.LayoutParams(0, dp(52), 1));
        Button reset = new Button(this);
        reset.setText("예제 문장");
        reset.setAllCaps(false);
        reset.setOnClickListener(v -> input.setText(SAMPLE));
        actions.addView(reset, new LinearLayout.LayoutParams(0, dp(52), 1));
        column.addView(actions);

        column.addView(text("한글 · 영문 · 숫자 · 문장부호", 17));
        TextView specimen = text("가나다라마바사아자차카타파하\n꽃 빛 삶 꿈 읽다 앉다 괜찮아\n과 왜 외 워 웨 위 의 꿰 뛴 쐐\nABCDEFGHIJKLMNOPQRSTUVWXYZ\nabcdefghijklmnopqrstuvwxyz\n0123456789 .,!? :; () [] {} +- = @#%&", 22);
        specimen.setTypeface(regular);
        specimen.setTextIsSelectable(true);
        column.addView(specimen);
        TextView footnote = text("한글 11,172자 · 영문 대소문자 지원\n15sp 이하에서는 작은 글자용 보정본을 자동 선택합니다.\n이 앱 안에서 손글씨를 미리볼 수 있습니다.", 12);
        footnote.setTextColor(Color.rgb(108, 116, 107));
        column.addView(footnote);
        column.addView(text("개인·기업·관공서 비상업적 사용 무료 · 상업적 이용 금지", 12));
        Button licenseButton = new Button(this);
        licenseButton.setText("폰트 라이선스");
        licenseButton.setAllCaps(false);
        licenseButton.setOnClickListener(v -> new android.app.AlertDialog.Builder(this)
            .setTitle("민보체 / minbo font 라이선스")
            .setMessage(readFontLicense()).setPositiveButton("확인", null).show());
        column.addView(licenseButton);

        seek.setOnSeekBarChangeListener(new SeekBar.OnSeekBarChangeListener() {
            @Override public void onProgressChanged(SeekBar bar, int progress, boolean fromUser) {
                size = progress + 7;
                optical.setChecked(size <= 15);
                updatePreview();
            }
            @Override public void onStartTrackingTouch(SeekBar bar) {}
            @Override public void onStopTrackingTouch(SeekBar bar) {}
        });
        optical.setOnCheckedChangeListener((button, checked) -> updatePreview());
        input.addTextChangedListener(new TextWatcher() {
            @Override public void beforeTextChanged(CharSequence s, int start, int count, int after) {}
            @Override public void onTextChanged(CharSequence s, int start, int before, int count) { updatePreview(); }
            @Override public void afterTextChanged(Editable s) {}
        });
        ScrollView scroll = new ScrollView(this);
        scroll.setFillViewport(true);
        scroll.setBackgroundColor(Color.rgb(250, 248, 241));
        scroll.setOnApplyWindowInsetsListener((view, insets) -> {
            view.setPadding(insets.getSystemWindowInsetLeft(), insets.getSystemWindowInsetTop(),
                insets.getSystemWindowInsetRight(), insets.getSystemWindowInsetBottom());
            return insets;
        });
        scroll.addView(column);
        scroll.setFocusableInTouchMode(true);
        setContentView(scroll);
        column.requestFocus();
        updatePreview();
    }

    private String readFontLicense() {
        try (java.io.InputStream stream = getResources().openRawResource(R.raw.font_license);
             java.io.ByteArrayOutputStream bytes = new java.io.ByteArrayOutputStream()) {
            byte[] buffer = new byte[4096];
            int count;
            while ((count = stream.read(buffer)) != -1) bytes.write(buffer, 0, count);
            return new String(bytes.toByteArray(), java.nio.charset.StandardCharsets.UTF_8);
        } catch (java.io.IOException exception) {
            throw new IllegalStateException("Font license could not be read", exception);
        }
    }

    @Override protected void onSaveInstanceState(Bundle outState) {
        outState.putString("input", input.getText().toString());
        outState.putInt("size", size);
        outState.putBoolean("optical", optical.isChecked());
        super.onSaveInstanceState(outState);
    }
}
